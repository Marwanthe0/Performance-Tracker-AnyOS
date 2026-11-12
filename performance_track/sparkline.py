"""
sparkline.py - Sparkline and text formatting utilities for Performance Track.
Provides Unicode block sparklines, progress bars, and human-readable byte formats.
"""

# Unicode block elements from low to high (8 levels)
SPARK_CHARS = [' ', '▂', '▃', '▄', '▅', '▆', '▇', '█']

def generate_sparkline(values, min_val=0.0, max_val=100.0):
    """
    Generate a compact Unicode sparkline string for a list or deque of numbers.
    Each character represents a point in time, with height corresponding to its value.
    """
    if not values:
        return ""
    
    val_range = max_val - min_val
    if val_range <= 0:
        val_range = 1.0

    chars = []
    for v in values:
        # Clamp value
        clamped = max(min_val, min(max_val, float(v)))
        # Map to 0..7
        normalized = (clamped - min_val) / val_range
        idx = int(normalized * (len(SPARK_CHARS) - 1) + 0.5)
        idx = max(0, min(len(SPARK_CHARS) - 1, idx))
        chars.append(SPARK_CHARS[idx])

    return "".join(chars)


def generate_bar(percent, width=10, fill_char='█', empty_char='░'):
    """
    Generate a text-based progress bar.
    Example: [████░░░░░░] 40%
    """
    pct = max(0.0, min(100.0, float(percent)))
    fill_len = int(round((pct / 100.0) * width))
    empty_len = width - fill_len
    return f"[{fill_char * fill_len}{empty_char * empty_len}]"


def format_bytes(num_bytes, suffix='B'):
    """
    Format a byte count into a human-readable string (KB, MB, GB, TB).
    """
    if num_bytes is None:
        return f"0.0 {suffix}"
    num_bytes = float(num_bytes)
    for unit in ['', 'K', 'M', 'G', 'T', 'P']:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}{suffix}".strip()
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} E{suffix}".strip()


def format_rate(bytes_per_sec):
    """
    Format bytes-per-second into human-readable throughput.
    Example: 124.5 KB/s, 12.3 MB/s
    """
    return format_bytes(bytes_per_sec, suffix='B/s')


def format_short_rate(bytes_per_sec):
    """
    Ultra-compact rate for topbar display.
    Example: 450B, 1.2K, 3.4M
    """
    if bytes_per_sec is None or bytes_per_sec <= 0:
        return "0B"
    b = float(bytes_per_sec)
    if b < 1024:
        return f"{b:.0f}B"
    elif b < 1024 * 1024:
        return f"{b/1024:.1f}K"
    elif b < 1024 * 1024 * 1024:
        return f"{b/(1024*1024):.1f}M"
    else:
        return f"{b/(1024*1024*1024):.1f}G"
