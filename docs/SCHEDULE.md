# Continuous schedule

Awake: every hour at minute 8, and a second trigger at minute 23 for continuity.
Sleep: every hour at minute 38.

Offset from :00/:30 to avoid peak-load drops.

Awake runs both arms in one `pair` job (control first, then treatment).
Sleep consolidates the treatment field. Control sleep is frozen and writes nothing.

Awake and sleep share the `nomad-continuous-data` concurrency group and retry rebase before push.
