import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
import type { PluggableList } from "unified";

import { markdownSanitizeSchema } from "./sanitize-schema.ts";

/** remark 插件链：仅 GFM，禁止 remark-html 等可注入 HTML 的插件。 */
export const markdownRemarkPlugins: PluggableList = [remarkGfm];

/** rehype 插件链：严格 sanitize，schema 见 sanitize-schema.ts。 */
export const markdownRehypePlugins: PluggableList = [[rehypeSanitize, markdownSanitizeSchema]];
