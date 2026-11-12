/**
 * extension.js - GNOME Shell 45/46 Extension for Ubuntu Performance Track.
 * Displays live CPU, RAM, and Performance Track metrics in the GNOME Top Bar.
 */

import { Extension, gettext as _ } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import GObject from 'gi://GObject';

const SPARK_CHARS = [' ', '▂', '▃', '▄', '▅', '▆', '▇', '█'];

function generateSparkline(values) {
    if (!values || values.length === 0) return '';
    return values.map(v => {
        let clamped = Math.max(0, Math.min(100, v));
        let idx = Math.min(7, Math.floor((clamped / 100) * 8));
        return SPARK_CHARS[idx];
    }).join('');
}

function formatBytes(bytes) {
    if (!bytes || bytes <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let idx = 0;
    let val = Number(bytes);
    while (val >= 1024 && idx < units.length - 1) {
        val /= 1024;
        idx++;
    }
    return `${val.toFixed(1)} ${units[idx]}`;
}

function formatShortRate(bytesPerSec) {
    if (!bytesPerSec || bytesPerSec <= 0) return '0B';
    let b = Number(bytesPerSec);
    if (b < 1024) return `${b.toFixed(0)}B`;
    if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)}K`;
    if (b < 1024 * 1024 * 1024) return `${(b / (1024 * 1024)).toFixed(1)}M`;
    return `${(b / (1024 * 1024 * 1024)).toFixed(1)}G`;
}

const PerformanceTrackIndicator = GObject.registerClass(
class PerformanceTrackIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, 'PerformanceTrackIndicator', false);

        this._prevCpu = null;
        this._prevNetRx = 0;
        this._prevNetTx = 0;
        this._prevTime = GLib.get_monotonic_time();
        this._cpuHistory = [];
        this._ramHistory = [];

        // Panel Container
        this._box = new St.BoxLayout({
            style_class: 'panel-status-menu-box',
            reactive: true,
            track_hover: true
        });

        // Icon
        this._icon = new St.Icon({
            icon_name: 'utilities-system-monitor-symbolic',
            style_class: 'system-status-icon'
        });
        this._box.add_child(this._icon);

        // Label
        this._label = new St.Label({
            text: 'CPU ... | RAM ...',
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'performancetrack-panel-label'
        });
        this._box.add_child(this._label);
        this.add_child(this._box);

        // Build Popup Menu
        this._buildMenu();

        // Initial update and periodic timer
        this._updateMetrics();
        this._timeoutId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 2, () => {
            this._updateMetrics();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _buildMenu() {
        // Header
        let titleItem = new PopupMenu.PopupMenuItem('📊 Performance Track Dashboard');
        titleItem.connect('activate', () => {
            try {
                let binPath = GLib.find_program_in_path('ubuntu-performance-track');
                if (!binPath) {
                    let home = GLib.get_home_dir();
                    binPath = `${home}/.local/bin/ubuntu-performance-track`;
                }
                let proc = new Gio.Subprocess({
                    argv: [binPath, '--dashboard'],
                    flags: Gio.SubprocessFlags.NONE
                });
                proc.init(null);
            } catch (e) {
                log(`[PerformanceTrack] Failed to open dashboard: ${e}`);
            }
        });
        this.menu.addMenuItem(titleItem);
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // CPU Section
        this._cpuMenuItem = new PopupMenu.PopupMenuItem('⚡ CPU: ...', { reactive: false });
        this.menu.addMenuItem(this._cpuMenuItem);

        // RAM Section
        this._ramMenuItem = new PopupMenu.PopupMenuItem('💾 RAM: ...', { reactive: false });
        this.menu.addMenuItem(this._ramMenuItem);

        // Track Section (Network / Disk)
        this._trackMenuItem = new PopupMenu.PopupMenuItem('🌐 Network: ...', { reactive: false });
        this.menu.addMenuItem(this._trackMenuItem);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // Launch GNOME System Monitor
        let sysMonItem = new PopupMenu.PopupMenuItem('🖥 Open GNOME System Monitor');
        sysMonItem.connect('activate', () => {
            try {
                let app = Gio.AppInfo.create_from_commandline('gnome-system-monitor', null, Gio.AppInfoCreateFlags.NONE);
                app.launch([], null);
            } catch (e) {
                log(`[PerformanceTrack] Failed to launch System Monitor: ${e}`);
            }
        });
        this.menu.addMenuItem(sysMonItem);
    }

    _readCpu() {
        try {
            let [ok, contents] = GLib.file_get_contents('/proc/stat');
            if (!ok) return null;
            let text = new TextDecoder().decode(contents);
            let firstLine = text.split('\n')[0];
            let parts = firstLine.trim().split(/\s+/).slice(1).map(Number);
            let idle = parts[3] + (parts[4] || 0);
            let total = parts.reduce((a, b) => a + b, 0);
            return { idle, total };
        } catch (e) {
            return null;
        }
    }

    _readMem() {
        try {
            let [ok, contents] = GLib.file_get_contents('/proc/meminfo');
            if (!ok) return null;
            let text = new TextDecoder().decode(contents);
            let totalMatch = text.match(/MemTotal:\s+(\d+)\s+kB/);
            let availMatch = text.match(/MemAvailable:\s+(\d+)\s+kB/);
            if (!totalMatch || !availMatch) return null;
            let totalBytes = parseInt(totalMatch[1]) * 1024;
            let availBytes = parseInt(availMatch[1]) * 1024;
            let usedBytes = Math.max(0, totalBytes - availBytes);
            let percent = totalBytes > 0 ? (usedBytes / totalBytes) * 100 : 0;
            return { totalBytes, usedBytes, availBytes, percent };
        } catch (e) {
            return null;
        }
    }

    _readNet() {
        try {
            let [ok, contents] = GLib.file_get_contents('/proc/net/dev');
            if (!ok) return { rx: 0, tx: 0 };
            let lines = new TextDecoder().decode(contents).split('\n').slice(2);
            let rxTotal = 0, txTotal = 0;
            for (let line of lines) {
                if (!line.includes(':')) continue;
                let [iface, data] = line.split(':');
                if (iface.trim() === 'lo') continue;
                let parts = data.trim().split(/\s+/).map(Number);
                if (parts.length >= 9) {
                    rxTotal += parts[0];
                    txTotal += parts[8];
                }
            }
            return { rx: rxTotal, tx: txTotal };
        } catch (e) {
            return { rx: 0, tx: 0 };
        }
    }

    _updateMetrics() {
        let now = GLib.get_monotonic_time();
        let dt = Math.max(0.001, (now - this._prevTime) / 1000000.0);
        this._prevTime = now;

        // 1. CPU
        let cpu = this._readCpu();
        let cpuPct = 0;
        if (cpu && this._prevCpu) {
            let dIdle = cpu.idle - this._prevCpu.idle;
            let dTotal = cpu.total - this._prevCpu.total;
            if (dTotal > 0) {
                cpuPct = Math.max(0, Math.min(100, (1 - dIdle / dTotal) * 100));
            }
        }
        this._prevCpu = cpu;

        // 2. RAM
        let mem = this._readMem();
        let ramPct = mem ? mem.percent : 0;

        // 3. Network Throughput
        let net = this._readNet();
        let rxRate = 0, txRate = 0;
        if (this._prevNetRx > 0 && net.rx >= this._prevNetRx) {
            rxRate = (net.rx - this._prevNetRx) / dt;
            txRate = (net.tx - this._prevNetTx) / dt;
        }
        this._prevNetRx = net.rx;
        this._prevNetTx = net.tx;

        // History
        this._cpuHistory.push(cpuPct);
        if (this._cpuHistory.length > 8) this._cpuHistory.shift();
        this._ramHistory.push(ramPct);
        if (this._ramHistory.length > 8) this._ramHistory.shift();

        // Update Topbar Label
        let usedG = mem ? (mem.usedBytes / (1024 ** 3)).toFixed(1) : '0';
        let spark = generateSparkline(this._cpuHistory);
        this._label.set_text(
            `CPU ${cpuPct.toFixed(0)}% ${spark} | RAM ${ramPct.toFixed(0)}% (${usedG}G) | ↓ ${formatShortRate(rxRate)}/s`
        );

        // Update Menu Items
        this._cpuMenuItem.label.set_text(`⚡ CPU Usage: ${cpuPct.toFixed(1)}%`);
        if (mem) {
            this._ramMenuItem.label.set_text(`💾 RAM Usage: ${formatBytes(mem.usedBytes)} / ${formatBytes(mem.totalBytes)} (${ramPct.toFixed(1)}%)`);
        }
        this._trackMenuItem.label.set_text(`🌐 Network Track: ↓ ${formatBytes(rxRate)}/s | ↑ ${formatBytes(txRate)}/s`);
    }

    destroy() {
        if (this._timeoutId) {
            GLib.source_remove(this._timeoutId);
            this._timeoutId = null;
        }
        super.destroy();
    }
});

export default class PerformanceTrackExtension extends Extension {
    enable() {
        this._indicator = new PerformanceTrackIndicator();
        Main.panel.addToStatusArea(this.uuid, this._indicator);
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
