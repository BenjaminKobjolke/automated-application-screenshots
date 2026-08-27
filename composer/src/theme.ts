/**
 * The tour's look, in one file.
 *
 * Change these and every caption and card follows; nothing else in the
 * composition hard-codes a colour or a size.
 */
export const theme = {
  // A stack, not one face: the render runs in headless Chrome, which has only
  // the fonts the machine has.
  fontFamily:
    '"Segoe UI", -apple-system, "Helvetica Neue", Arial, sans-serif',
  background: '#0d0f13',
  text: '#ffffff',
  muted: 'rgba(255, 255, 255, 0.72)',
  accent: '#4da3ff',

  caption: {
    // Relative to the composition height, so one theme fits 720p and 1080p.
    fontSize: 0.038,
    paddingX: 0.022,
    paddingY: 0.014,
    // Distance from the bottom edge; clear of most status bars.
    bottom: 0.06,
    radius: 10,
    background: 'rgba(0, 0, 0, 0.66)',
    // Frames of fade at each end of a caption's life.
    fadeFrames: 12,
  },

  card: {
    titleSize: 0.1,
    subtitleSize: 0.042,
    fadeFrames: 15,
  },
} as const;
