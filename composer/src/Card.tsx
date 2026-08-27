import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {theme} from './theme';

export type CardProps = {
  title: string;
  subtitle?: string | null;
};

/** A full-frame title card: the tour's opening and closing frames. */
export const Card: React.FC<CardProps & {durationInFrames: number}> = ({
  title,
  subtitle,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const {height} = useVideoConfig();
  const fade = theme.card.fadeFrames;

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
        background: theme.background,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: height * 0.02,
        fontFamily: theme.fontFamily,
        opacity,
      }}
    >
      <div
        style={{
          fontSize: height * theme.card.titleSize,
          color: theme.text,
          fontWeight: 600,
          letterSpacing: '-0.02em',
        }}
      >
        {title}
      </div>
      {subtitle ? (
        <div style={{fontSize: height * theme.card.subtitleSize, color: theme.muted}}>
          {subtitle}
        </div>
      ) : null}
    </div>
  );
};
