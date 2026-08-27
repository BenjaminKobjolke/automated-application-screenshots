# Publishing the results

## Artifacts vs intermediates

Recording produces intermediates; composing produces the artifact. Only the
artifact belongs in the repository:

| Keep | Ignore |
|---|---|
| the composed tour MP4 | the per-chapter `demos/tour-*/` clips |
| the themes GIF | the per-theme `demos/themes/*.png` stills |
| the feature GIFs | the `demos/feature-*/` MP4s they came from |
| overview stills used directly in the README | everything else under `demos/` |

```gitignore
media/demos/tour-*/
media/demos/feature-*/
media/demos/themes/*.png
```

The intermediates are reproducible from the config and the app, and they are
large. The artifact is what a reader downloads, so it is the thing worth
reviewing in a diff — and the thing worth a `max_size` budget
(see [CONFIG.md](CONFIG.md#size-budgets)).

## GitHub: video vs GIF

GitHub renders an inline **video player** only for an attachment URL that is
alone on its own line:

```markdown
https://github.com/user-attachments/assets/<uuid>
```

Any other form — a markdown link, a relative path to a committed MP4, a URL with
text beside it — renders as a link, not a player. Two consequences that surprise
everyone once:

1. **The committed MP4 and the video the README plays are two different files.**
   The repository holds the artifact; the README references an uploaded
   attachment. Re-record and you have to re-upload, or the README keeps playing
   the old take.
2. **A video cannot sit next to a paragraph.** Anything inline — a feature list
   where each entry has its own moving image — has to be a GIF, which is why the
   `mp4_gif` compose step exists.

Attachments are created by dragging a file into any issue, PR or comment box on
github.com and copying the resulting `user-attachments` URL (without posting).
The `gh image` extension (`gh extension install drogers0/gh-image`) does the same
from the command line.

## A README that stays honest

- Reference committed stills and GIFs by **relative path**, so a fork and a
  local clone both show them.
- Use the attachment URL only for the one big tour video.
- Re-run `--compose` rather than editing an artifact by hand; an artifact nobody
  can rebuild is worse than no artifact.
