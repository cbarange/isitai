# isitai

Work in progress. Not usable yet.

`isitai` will check, locally and offline, whether a text or a file carries **proof** or **signals** that it was made by AI:

- signed C2PA Content Credentials (images, video, audio, PDF);
- IPTC `DigitalSourceType` metadata;
- metadata left by image generators (Stable Diffusion, ComfyUI…);
- copy-paste artifacts in text.

It does not guess. A file without signal is reported as `no-signal`, never as "human".

Version 0.1.0 will ship a Rust core with Node.js and Python bindings.
