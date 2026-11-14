"""Navigate a browser page to a configured fragment before capturing it."""

from playwright.sync_api import Page

FRAGMENT_SETTLE_TIMEOUT_MS = 2000

_SCROLL_TO_FRAGMENT_JS = f"""async (fragment) => {{
  let name;
  try {{
    name = decodeURIComponent(fragment);
  }} catch (_) {{
    name = fragment;
  }}

  const target = document.getElementById(name) || document.getElementsByName(name)[0];
  if (!target) return false;

  const root = document.documentElement;
  const previousScrollBehavior = root.style.scrollBehavior;
  root.style.scrollBehavior = 'auto';
  target.scrollIntoView({{ block: 'start', inline: 'nearest', behavior: 'instant' }});
  root.style.scrollBehavior = previousScrollBehavior;

  const deadline = performance.now() + {FRAGMENT_SETTLE_TIMEOUT_MS};
  let previousX = window.scrollX;
  let previousY = window.scrollY;
  let stableFrames = 0;
  while (stableFrames < 2 && performance.now() < deadline) {{
    await new Promise(requestAnimationFrame);
    if (window.scrollX === previousX && window.scrollY === previousY) {{
      stableFrames += 1;
    }} else {{
      stableFrames = 0;
      previousX = window.scrollX;
      previousY = window.scrollY;
    }}
  }}

  const runningAnimations = document.getAnimations().filter((animation) =>
    animation.playState === 'running' &&
    animation.effect?.getTiming().iterations !== Infinity
  );
  await Promise.all(runningAnimations.map((animation) => Promise.race([
    animation.finished.catch(() => {{}}),
    new Promise((resolve) => setTimeout(resolve, {FRAGMENT_SETTLE_TIMEOUT_MS})),
  ])));
  return true;
}}"""


def scroll_to_fragment(page: Page, fragment: str) -> bool:
    """Scroll instantly to a fragment target and wait for page motion to settle."""
    return page.evaluate(_SCROLL_TO_FRAGMENT_JS, fragment)
