> ### Fork notice
> This is a **modified fork** of [Metachs/sdwebui-nai-api](https://github.com/Metachs/sdwebui-nai-api).
> It is not the original software and is not endorsed by the original author.
> Original work and license by Metachs; see `LICENSE`.
>
> It tracks upstream (including upstream's own NovelAI Diffusion V5 support) and adds
> transparent backgrounds, Enhance/upscale, some corrected V5 presets, and a few bug fixes.

# sdwebui-nai-api - Novel AI Image Gen in stable-diffusion webui

### An an extension for A1111's stable-diffusion-webui that pulls images using NovelAI's Image Generation Tool API.

#### Requires an active Novel AI account with Opus or Anlas to spend (NOT FREE). You will need to generate a NovelAI API Token for your account, and enter it into the NAI API section in sd-webui settings menu. See [https://docs.sillytavern.app/usage/api-connections/novelai] for details on generating an API key.

Install using "Extensions > Install from URL" using the repo's URL.

- Supports Text2Image, Image2Image, and Inpainting using NovelAI's API
- Supports an A1111 style img2img inpainting mode with an adjustable Denoise Strength.
- Supports a number of A1111 scripts/extensions, such as XYZ Grid generation, Wildcards, Adetailer, SD Upscale
- Allows much higher precision Inpainting masks, as well as uploading masks from other sources.
- Allows feeding NAI generations directly into A1111's Local Image2Image, for a sort of multi-model hi-res fix.
- Automatically translates A1111 format weighted prompts to NovelAI's format eg (1girl:1.1) > {{1girl}} (Values can't be 1:1, but should be close enough)
- Includes a modified version of the Stealth PNG Info extension to fully support NovelAI's stealth PNG info, for sites that strip metadata.
- Optionally Enforces Opus' Free generation limits to avoid wasting Anlas
- Always download every generated image, with A1111's custom filename support

## What this fork adds on top of upstream

### Transparent Background (V5)
A checkbox that adds `transparent background` to the prompt and sets `tag_hint_transparent_background`,
matching the site's "Transparent BG" toggle. Save as **PNG** - JPEG/WebP discard the alpha channel.

### Enhance / Upscale
The site's Enhance feature: a second img2img pass at a larger size, at `1.5x`, `2x`, or `Max`,
with a Magnitude slider (1-5) using the same strength/noise pairs the website does.

**This spends Anlas.** It is not covered by the Opus free-generation allowance - an 832x1216 image
enhanced to 1.5x cost 27 Anlas in testing. Scales whose output would exceed NovelAI's pixel ceiling
are skipped with a message rather than sent and rejected.

### V5 preset corrections
Checked against NovelAI's current web client:
- V5 Curated uses the same quality preset as V5 Full (`very aesthetic, masterpiece, no text`).
- V5 has its own "light" Undesired Content preset, distinct from V4.5's.
- V5 Curated shares V5 Full's UC preset list.
- V4.5 Curated keeps its `very aesthetic` prefix.

### V5 request shaping
- Noise schedule forced to `karras` - V5 exposes no schedule option and the site always sends karras.
- `skip_cfg_above_sigma` disabled, since V5 has no Variety+ / cfg delay.
- `ddim` mapped to `k_euler_ancestral`, as the site does for V4 and V5.
- Vibe Transfer and Character Reference dropped with a warning on V5 - NovelAI has not shipped them
  for this model yet, so sending them would only produce an API error.

### Fixes
- Handles the `retry` event NovelAI's generation stream now emits, instead of logging it as an unknown
  event and letting it contaminate unrelated error messages.
- Live previews no longer freeze after a server-side retry restarts the step counter.
- Stealth PNG info no longer forces the alpha channel opaque, which destroyed genuine transparency
  on V5 output.
- Fixed a `NameError` that crashed any generation using the `ddim` sampler.

## Your API key

The key is stored by the webui in its own `config.json` under `nai_api_key`, outside this extension's
folder, and is never written to any file here.

On Colab or any throwaway environment, leave that field blank and supply the key as an
environment variable named `NAI_API_KEY`, or as a Colab secret of the same name. That keeps it
out of notebook cells and saved output. The Settings field takes priority when it is set. Nothing in this repository contains credentials.
Treat your key like a password: it is tied to your NovelAI account and spends your Anlas.


Most locally run extension are NOT supported, obviously. Anything that alter's model behavior is a no go. 
It does support basic extensions/Scripts that only modify generation parameters such as wildcards, or intiate generation, such as XYZ Grid, ADetailer, and SD Upscale.
Running this with certain extensions on may break things. 
 
### Note that this is compltely unaffiliated with NovelAI, and I can make no guarantees as to whether this is an allowable usage of Novel AI's services. However, since they provide the means for you to generate an API Token, I believe it is an acceptable use. IE use at you own risk, but you are probably ok if you don't do something stupid like leave generate forever on for days.


#### Unsupported/TODO
- NAI ControlNet Tools - Not sure how CN works in NAI, not worth worrying about until NAIv3 supports 'em
- NAI Batch support - This isn't free in the only NAI offering worth paying for, so I haven't bothered. (A1111 Batches are pulled sequentially)
- Separate Prompts for NAI/Local in Two pass Image2Image mode.
