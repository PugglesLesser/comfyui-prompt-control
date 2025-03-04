import logging
from .parser import parse_prompt_schedules
import math

log = logging.getLogger("comfyui-prompt-control")


def template(template, sequence, *funcs):
    funcs = [lambda x: x] + list(*funcs)
    res = []
    for item in sequence:
        x = template
        for i, f in enumerate(funcs):
            x = x.replace(f"${i}", str(f(i)))
        res.append(x)

    return "".join(res)

def steps(start, end=None, step=0.1):
    if end is None:
        end = start
        start = step
    while start <= end:
        yield start
        start += step
        start = round(start, 2)


class StringConcat:
    @classmethod
    def INPUT_TYPES(s):
        t = ("STRING", {"default": ""})
        return {
            "optional": {
                "string1": t,
                "string2": t,
                "string3": t,
                "string4": t,
            }
        }

    RETURN_TYPES = ("STRING",)

    CATEGORY = "promptcontrol/tools"
    FUNCTION = "cat"

    def cat(self, string1="", string2="", string3="", string4=""):
        return string1 + string2 + string3 + string4


def filter_schedule(schedule, remove_before, remove_after):
    r = []
    for t, s in schedule:
        if t < remove_before:
            continue
        elif t <= remove_after:
            r.append((t, s))
        elif t >= remove_after:
            break
    if len(r) == 0:
        # Take the last item if nothing would be returned
        r = [(1.0, schedule[-1][1])]
    # Extend the last item to the end of the prompt
    r[-1] = (1.0, r[-1][1])
    return r


class FilterSchedule:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {"prompt_schedule": ("PROMPT_SCHEDULE",)},
            "optional": {
                "remove_ending_before": ("FLOAT", {"min": 0.00, "max": 1.00, "default": 0.0, "step": 0.01}),
                "remove_starting_after": ("FLOAT", {"min": 0.00, "max": 1.00, "default": 1.0, "step": 0.01}),
            },
        }

    RETURN_TYPES = ("PROMPT_SCHEDULE",)
    CATEGORY = "promptcontrol/tools"
    FUNCTION = "apply"

    def apply(self, prompt_schedule, remove_ending_before=0.0, remove_starting_after=1.0):
        s = filter_schedule(prompt_schedule, remove_ending_before, remove_starting_after)
        log.debug("Filtered %s (%s,%s), received %s", prompt_schedule, remove_ending_before, remove_starting_after, s)
        return (s,)


class PromptToSchedule:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "text": ("STRING", {"multiline": True}),
            },
            "optional": {
                "filter_tags": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("PROMPT_SCHEDULE",)
    CATEGORY = "promptcontrol"
    FUNCTION = "parse"

    def parse(self, text, filter_tags=""):
        schedules = parse_prompt_schedules(text, filter_tags)
        return (schedules,)

def clamp(a, b, c):
    return max(a, min(b, c))

JINJA_ENV = {'pi': math.pi, 
             'floor': math.floor, 
             'ceil': math.ceil,
             'min': min,
             'max': max,
             'abs': abs,
             'clamp': clamp,
             'round': round,
             'template': template,
             'steps': steps,
            }

for fname in ['sqrt', 'sin', 'cos', 'tan', 'asin', 'acos', 'atan']:
    f = getattr(math, fname)
    JINJA_ENV[fname] = lambda x: round(f(x), 2)

class JinjaRender:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"text": ("STRING", {"default": "", "multiline": True})}}

    RETURN_TYPES = ("STRING",)

    CATEGORY = "promptcontrol/tools"
    FUNCTION = "render"

    def render(self, text):
        from jinja2 import Environment

        jenv = Environment(
            block_start_string="<%",
            block_end_string="%>",
            variable_start_string="<=",
            variable_end_string="=>",
            comment_start_string="<#",
            comment_end_string="#>",
        )

        s = jenv.from_string(text, globals=JINJA_ENV).render()
        return (s,)


class ConditioningCutoff:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "conds": ("CONDITIONING",),
                "cutoff": ("FLOAT", {"min": 0.00, "max": 1.00, "default": 0.0, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("CONDITIONING",)
    CATEGORY = "promptcontrol/tools"
    FUNCTION = "apply"

    def apply(self, conds, cutoff):
        res = []
        new_start = 1.0
        for c in conds:
            end = c[1].get("end_percent", 0.0)
            if 1.0 - end < cutoff:
                log.debug("Chose to remove prompt '%s'", c[1].get("prompt", "N/A"))
                continue
            c = [c[0].clone(), c[1].copy()]
            c[1]["start_percent"] = new_start
            c[1]["end_percent"] = end
            new_start = end
            res.append(c)

        log.debug("Conds after filter: %s", [(c[1]["prompt"], c[1]["start_percent"], c[1]["end_percent"]) for c in res])
        return (res,)
