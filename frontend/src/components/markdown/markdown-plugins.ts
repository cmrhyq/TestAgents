import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
import type { PluggableList } from "unified";

import { markdownSanitizeSchema } from "./sanitize-schema.ts";

/** remark 插件链：仅启用 GFM，不引入可注入 HTML 的插件。 */
export const markdownRemarkPlugins: PluggableList = [remarkGfm];

/** rehype 插件链：严格 sanitize，白名单见 `sanitize-schema.ts`。 */
export const markdownRehypePlugins: PluggableList = [[rehypeSanitize, markdownSanitizeSchema]];
