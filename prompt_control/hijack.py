from .utils import get_callback, unpatch_model
import comfy.sample
import sys

import logging

log = logging.getLogger("comfyui-prompt-control")


def do_hijack():
    orig_sampler = comfy.sample.sample
    if hasattr(comfy.sample.sample, "pc_hijack_done"):
        return

    def pc_sample(*args, **kwargs):
        model = args[0]
        cb = get_callback(model)
        if cb:
            try:
                return cb(orig_sampler, *args, **kwargs)
            except Exception:
                log.info("Exception occurred during callback, unpatching model...")
                unpatch_model(model)
                raise
        else:
            return orig_sampler(*args, **kwargs)

    comfy.sample.sample = pc_sample

    try:
        global aitemplate_mod
        log.info("AITemplate detected, hijacking...")
        AITLoader = sys.modules["AIT.AITemplate.ait.load"].AITLoader
        orig_apply_unet = AITLoader.apply_unet

        def apply_unet(self, *args, **kwargs):
            setattr(self, "pc_applied_module", kwargs["aitemplate_module"])
            return orig_apply_unet(self, *args, **kwargs)

        AITLoader.apply_unet = apply_unet
        log.info("AITemplate hijack complete")
    except Exception:
        log.info("AITemplate hijack failed or not necessary")

    setattr(comfy.sample.sample, "pc_hijack_done", True)
