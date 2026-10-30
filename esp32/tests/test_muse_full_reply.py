# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Full-screen replies on small screens (CONFIG_MUSE_SMALL_FULL_REPLY): the
caption keeps the screen for every page of a reply, with or without CJK, its
pages fit the caption buffer, and the band comes back when the reply ends.

The layout functions are compiled from muse_ui.c unchanged, against a fake
LVGL that records the caption label's geometry and font."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "components" / "muse" / "muse_ui.c"

HARNESS = r"""
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include "muse_settings.h"

#define MUSE_CAPTION_MAX 400
#define CAPTION_LINE_SPACE 2
#define TAG "muse_ui"
#define ESP_LOGI(...) ((void)0)

typedef struct { int line_h, glyph_w; } lv_font_t;
static const lv_font_t lv_font_unscii_8 = { 8, 8 };
static const lv_font_t lv_font_unscii_16 = { 16, 8 };
static const lv_font_t lv_font_montserrat_14 = { 16, 8 };
static const lv_font_t lv_font_montserrat_20 = { 22, 11 };
static const lv_font_t cjk_font = { 16, 8 };   /* unscii-16 with the CJK fallback */
static const lv_font_t *caption_font(void) { return &cjk_font; }
static int lv_font_get_line_height(const lv_font_t *f) { return f->line_h; }
static int lv_font_get_glyph_width(const lv_font_t *f, int c, int next) { (void)c; (void)next; return f->glyph_w; }

typedef struct { int w, h, pad_hor, line_space, opa, long_mode, align, y; bool hidden; const lv_font_t *font; } lv_obj_t;
enum { LV_OPA_70 = 178, LV_OPA_COVER = 255 };
enum { LV_LABEL_LONG_MODE_WRAP, LV_LABEL_LONG_MODE_DOTS };
enum { LV_ALIGN_TOP_MID, LV_ALIGN_BOTTOM_MID };
enum { LV_OBJ_FLAG_HIDDEN = 1 };
static void lv_obj_set_size(lv_obj_t *o, int w, int h) { o->w = w; o->h = h; }
static void lv_obj_set_height(lv_obj_t *o, int h) { o->h = h; }
static void lv_obj_set_style_text_font(lv_obj_t *o, const lv_font_t *f, int s) { (void)s; o->font = f; }
static void lv_obj_set_style_text_line_space(lv_obj_t *o, int v, int s) { (void)s; o->line_space = v; }
static void lv_obj_set_style_pad_hor(lv_obj_t *o, int v, int s) { (void)s; o->pad_hor = v; }
static void lv_obj_set_style_bg_opa(lv_obj_t *o, int v, int s) { (void)s; o->opa = v; }
static void lv_label_set_long_mode(lv_obj_t *o, int m) { o->long_mode = m; }
static void lv_obj_align(lv_obj_t *o, int a, int x, int y) { (void)x; o->align = a; o->y = y; }
static void lv_obj_set_flag(lv_obj_t *o, int f, bool on) { (void)f; o->hidden = on; }

static int s_size = MUSE_TEXT_MEDIUM;
int muse_settings_text_size(void) { return s_size; }
static int s_cols, s_lines, s_cjk_cols, s_cjk_page_lines;
void muse_state_set_page(int cols, int lines) { s_cols = cols; s_lines = lines; }
void muse_state_set_cjk_page(int cols, int lines) { s_cjk_cols = cols; s_cjk_page_lines = lines; }

static lv_obj_t caption_obj, canvas_obj;
static lv_obj_t *s_caption_lbl = &caption_obj, *s_canvas = &canvas_obj;
static int s_w = 172, s_h = 320;
static bool s_tall = true, s_tv = false;

#include "extracted.inc"

static int failures;
#define CHECK(cond, ...) do { if (!(cond)) { failures++; printf("FAIL %s:%d: ", __func__, __LINE__); printf(__VA_ARGS__); printf("\n"); } } while (0)

static bool fits(int cols, int lines) { return (cols + 1) * lines <= MUSE_CAPTION_MAX * 2 / 3; }

static void full(const char *step)
{
    CHECK(caption_obj.h == s_full_reply_h && caption_obj.w == s_w, "%s: caption is %dx%d, not the full screen %dx%d",
          step, caption_obj.w, caption_obj.h, s_w, s_full_reply_h);
    CHECK(caption_obj.long_mode == LV_LABEL_LONG_MODE_WRAP && caption_obj.opa == LV_OPA_COVER, "%s: not wrapped on black", step);
    CHECK(canvas_obj.hidden, "%s: Muse still shown", step);
}

int main(void)
{
    /* build_screen's band, then the option's setup. */
    lv_obj_set_size(s_caption_lbl, s_w, 2 * 8 + 2 + 4);
    lv_obj_set_style_text_font(s_caption_lbl, &lv_font_unscii_8, 0);
    lv_obj_set_style_text_line_space(s_caption_lbl, 2, 0);
    lv_label_set_long_mode(s_caption_lbl, LV_LABEL_LONG_MODE_DOTS);
    lv_obj_set_style_bg_opa(s_caption_lbl, LV_OPA_70, 0);
#if CONFIG_MUSE_CJK_FONT
    s_cjk_lines = 1;
    muse_state_set_cjk_page((s_w - 2 * CJK_BAND_PAD) / 8, s_cjk_lines);
#endif
    s_full_reply_h = s_h - FULL_REPLY_TOP - 6;
    s_band_font = &lv_font_unscii_8;
    for (s_size = MUSE_TEXT_LARGE; s_size >= MUSE_TEXT_SMALL; s_size--) {
        apply_text_size();
        CHECK(s_lines > 2 && fits(s_cols, s_lines), "size %d: page %dx%d", s_size, s_cols, s_lines);
    }
    s_size = MUSE_TEXT_MEDIUM;
    apply_text_size();
    const lv_font_t *medium = &lv_font_montserrat_14;
#if CONFIG_MUSE_CJK_FONT
    int lines_h = s_cjk_page_lines * 16 + (s_cjk_page_lines - 1) * CJK_LINE_SPACE;
    CHECK(s_cjk_page_lines > s_cjk_lines && fits(s_cjk_cols, s_cjk_page_lines) && lines_h <= s_full_reply_h - 4,
          "CJK page %dx%d is the band's or doesn't fit the screen and buffer", s_cjk_cols, s_cjk_page_lines);
#endif

    /* A reply: the first page, then the next ones as they come. */
#if CONFIG_MUSE_CJK_FONT
    set_caption_font(false);
#endif
    set_full_reply(true);
    full("first page");
    CHECK(caption_obj.font == medium, "first page: not the Text size font");
#if CONFIG_MUSE_CJK_FONT
    set_caption_font(false);
    full("next page");
    CHECK(caption_obj.font == medium, "next page: not the Text size font");
    set_caption_font(true);
    full("CJK page");
    CHECK(caption_obj.font == &cjk_font, "CJK page: not the caption font");
    s_size = MUSE_TEXT_LARGE;
    apply_text_size();
    full("Text size changed");
    CHECK(caption_obj.font == &cjk_font, "Text size changed: CJK lost its font");
    set_full_reply(false);
    CHECK(!canvas_obj.hidden && caption_obj.long_mode == LV_LABEL_LONG_MODE_DOTS, "reply over: no band");
    CHECK(caption_obj.font == &cjk_font && caption_obj.h == 16 + 6 && caption_obj.pad_hor == CJK_BAND_PAD,
          "reply over: not the CJK band (h %d)", caption_obj.h);
    set_caption_font(false);
    CHECK(caption_obj.font == &lv_font_unscii_8 && caption_obj.h == 2 * 8 + 2 + 4, "band: not two lines of unscii-8");
#else
    set_full_reply(false);
    CHECK(!canvas_obj.hidden && caption_obj.long_mode == LV_LABEL_LONG_MODE_DOTS, "reply over: no band");
    CHECK(caption_obj.font == &lv_font_unscii_8 && caption_obj.h == 2 * 8 + 2 + 4 && caption_obj.pad_hor == 0,
          "reply over: not the band");
#endif
    printf("%s\n", failures ? "FAILED" : "OK");
    return failures != 0;
}
"""


def function(source: str, name: str) -> str:
    """One whole function definition from muse_ui.c, or "" if it isn't there."""
    match = re.search(r"^static void " + name + r"\(", source, re.M)
    if not match:
        return ""
    start = match.start()
    end = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end] + "\n"


def extract(source: str) -> str:
    statics = re.search(r"^#if CONFIG_MUSE_SMALL_FULL_REPLY\n#define FULL_REPLY_TOP.*?^#endif\n", source, re.M | re.S)
    cjk = re.search(r"^#define CJK_BAND_PAD.*?(?=^/\*.*\n.*\*/\nstatic void set_caption_font)", source, re.M | re.S)
    if not statics or not cjk:
        raise AssertionError("muse_ui.c no longer has the full-reply statics or the CJK band")
    parts = [statics.group(0), "#if CONFIG_MUSE_CJK_FONT\n", cjk.group(0), function(source, "set_caption_font"), "#endif\n"]
    for name in ("set_full_font", "apply_text_size", "set_full_reply"):
        parts.append(function(source, name))
    return "".join(parts)


@unittest.skipUnless(shutil.which(shlex.split(os.environ.get("CC", "cc"))[0]), "C compiler not available")
class FullReplyTest(unittest.TestCase):
    def run_harness(self, cjk: bool) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            (stage / "esp_err.h").write_text("#pragma once\ntypedef int esp_err_t;\n")
            shutil.copyfile(ROOT / "components" / "muse" / "muse_settings.h", stage / "muse_settings.h")
            (stage / "extracted.inc").write_text(extract(UI.read_text()))
            (stage / "harness.c").write_text(HARNESS)
            binary = stage / "harness"
            build = subprocess.run(
                [*shlex.split(os.environ.get("CC", "cc")), "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                 "-Wno-unused-function", "-Wno-unused-variable", "-Wno-unused-but-set-variable",
                 "-DCONFIG_MUSE_SMALL_FULL_REPLY=1", f"-DCONFIG_MUSE_CJK_FONT={int(cjk)}",
                 "-I", str(stage), str(stage / "harness.c"), "-o", str(binary)],
                text=True, capture_output=True,
            )
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(binary)], text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_without_cjk_font(self) -> None:
        self.run_harness(cjk=False)

    def test_with_cjk_font(self) -> None:
        """Main's CJK band resizes the caption on every caption: not while a reply has the screen."""
        self.run_harness(cjk=True)


if __name__ == "__main__":
    unittest.main()
