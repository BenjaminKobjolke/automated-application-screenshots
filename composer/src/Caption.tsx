import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {theme} from './theme';

/**
 * A chapter title, held over the first seconds of its clip.
 *
 * It titles the chapter rather than narrating it, so it leaves before it can
 * cover the part of the UI the chapter is about.
 */
export const Caption: React.FC<{text: string; durationInFrames: number}> = ({
  text,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const {height} = useVideoConfig();
  const fade = theme.caption.fadeFrames;

  if (!text || frame > durationInFrames) {
    return null;
  }

  const opacity = interpolate(
    frame,
    [0, fade, Math.max(fade, durationInFrames - fade), durationInFrames],
    [0, 1, 1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
  );

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
        paddingBottom: height * theme.caption.bottom,
        opacity,
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          fontFamily: theme.fontFamily,
          fontSize: height * theme.caption.fontSize,
          color: theme.text,
          background: theme.caption.background,
          padding: `${height * theme.caption.paddingY}px ${
            height * theme.caption.paddingX
          }px`,
          borderRadius: theme.caption.radius,
          // Long captions wrap instead of running off the frame, which is the
          // thing ffmpeg's drawtext could never do.
          maxWidth: '82%',
          textAlign: 'center',
          lineHeight: 1.3,
        }}
      >
        {text}
      </div>
    </div>
  );
};
