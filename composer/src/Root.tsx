import React from 'react';
import {Composition} from 'remotion';
import {Tour, TourProps} from './Tour';

/**
 * Everything about the tour's size and length comes from the props file that
 * screenshot_tool/compose/tour.py writes, so this file never has to change
 * when a chapter is added.
 *
 * The defaults exist only so `npm run studio` opens on something.
 */
const defaultProps: TourProps = {
  fps: 30,
  width: 1280,
  height: 800,
  totalFrames: 300,
  captionFrames: 150,
  clips: [],
  intro: {title: 'Your app', subtitle: 'a feature tour', durationInFrames: 90},
  outro: null,
};

export const RemotionRoot: React.FC = () => (
  <Composition
    id="Tour"
    component={Tour}
    durationInFrames={defaultProps.totalFrames}
    fps={defaultProps.fps}
    width={defaultProps.width}
    height={defaultProps.height}
    defaultProps={defaultProps}
    calculateMetadata={({props}) => ({
      // Pure arithmetic on the props - no media probing here. The Python side
      // already measured every clip with ffmpeg, which is the same number and
      // one less thing to go wrong inside headless Chrome.
      durationInFrames: Math.max(1, props.totalFrames),
      fps: props.fps,
      width: props.width,
      height: props.height,
    })}
  />
);
