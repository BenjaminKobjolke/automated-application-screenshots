import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  OffthreadVideo,
  Series,
  staticFile,
  useCurrentFrame,
} from 'remotion';
import {Caption} from './Caption';
import {Card, CardProps} from './Card';
import {theme} from './theme';

export type Clip = {
  /** Path relative to the public dir, which is the recorder's output folder. */
  src: string;
  durationInFrames: number;
  caption?: string | null;
};

export type TourProps = {
  fps: number;
  width: number;
  height: number;
  totalFrames: number;
  captionFrames: number;
  clips: Clip[];
  intro?: (CardProps & {durationInFrames: number}) | null;
  outro?: (CardProps & {durationInFrames: number}) | null;
};

/** One chapter: its clip, a fade in from black, and its caption. */
const Chapter: React.FC<{clip: Clip; captionFrames: number}> = ({
  clip,
  captionFrames,
}) => {
  const frame = useCurrentFrame();
  // Chapters are separate takes, so they cut hard. A short fade in makes the
  // seam read as an edit instead of a glitch.
  const opacity = interpolate(frame, [0, 8], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <AbsoluteFill style={{background: theme.background}}>
      <AbsoluteFill style={{opacity}}>
        <OffthreadVideo src={staticFile(clip.src)} />
      </AbsoluteFill>
      {clip.caption ? (
        <Caption text={clip.caption} durationInFrames={captionFrames} />
      ) : null}
    </AbsoluteFill>
  );
};

export const Tour: React.FC<TourProps> = ({
  clips,
  captionFrames,
  intro,
  outro,
}) => (
  <AbsoluteFill style={{background: theme.background}}>
    <Series>
      {intro ? (
        <Series.Sequence durationInFrames={intro.durationInFrames}>
          <Card {...intro} />
        </Series.Sequence>
      ) : null}
      {clips.map((clip, index) => (
        <Series.Sequence key={`${clip.src}-${index}`} durationInFrames={clip.durationInFrames}>
          <Chapter clip={clip} captionFrames={captionFrames} />
        </Series.Sequence>
      ))}
      {outro ? (
        <Series.Sequence durationInFrames={outro.durationInFrames}>
          <Card {...outro} />
        </Series.Sequence>
      ) : null}
    </Series>
  </AbsoluteFill>
);
