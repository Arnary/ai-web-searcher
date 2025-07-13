import base64
import os

from tenacity import retry, stop_after_attempt, wait_fixed
from langchain_core.runnables import chain as chain_decorator


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
JS_PATH = os.path.normpath(os.path.join(CURRENT_DIR, '..', 'static', 'js', 'mark_page.js'))

with open(JS_PATH) as f:
    MARK_PAGE_SCRIPT = f.read()


@retry(stop=stop_after_attempt(10), wait=wait_fixed(3))
async def try_mark_page(page):
    return await page.evaluate("markPage()")

@chain_decorator
async def mark_page(page):
    await page.evaluate(MARK_PAGE_SCRIPT)
    bboxes = await try_mark_page(page)
    screenshot = await page.screenshot()
    await page.evaluate("unmarkPage()")
    return {
        "img": base64.b64encode(screenshot).decode(),
        "bboxes": bboxes,
    }


async def annotate(state):
    marked_page = await mark_page.with_retry().ainvoke(state["page"])
    return {**state, **marked_page}


def format_descriptions(state):
    labels = []
    for i, bbox in enumerate(state["bboxes"]):
        text = bbox.get("ariaLabel") or ""
        if not text.strip():
            text = bbox["text"]
        el_type = bbox.get("type")
        labels.append(f'{i} (<{el_type}/>): "{text}"')
    bbox_descriptions = "\nValid Bounding Boxes:\n" + "\n".join(labels)
    return {**state, "bbox_descriptions": bbox_descriptions}


def parse(text: str) -> dict:
    action_prefix = "Action: "
    if not text.strip().split("\n")[-1].startswith(action_prefix):
        return {"action": "retry", "args": f"Could not parse LLM Output: {text}"}

    action_block = text.strip().split("\n")[-1]
    action_str = action_block[len(action_prefix):]
    split_output = action_str.split(" ", 1)

    if len(split_output) == 1:
        action, action_input = split_output[0], None
    else:
        action, action_input = split_output

    action = action.strip()
    if action_input is not None:
        action_input = [inp.strip().strip("[]") for inp in action_input.strip().split(";")]

    return {"action": action, "args": action_input}
