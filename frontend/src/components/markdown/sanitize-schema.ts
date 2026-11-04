import { defaultSchema, type Options as SanitizeSchema } from "rehype-sanitize";

/**
 * rehype-sanitize 白名单：在 GitHub 默认规则之上仅放开代码高亮所需的 `className`。
 *
 * 不渲染原始 HTML、脚本与事件处理器；`img` 从 tagNames 中移除，远程图片不加载。
 */
export const markdownSanitizeSchema: SanitizeSchema = {
  ...defaultSchema,
  tagNames: defaultSchema.tagNames?.filter((tag) => tag !== "img"),
  attributes: {
    ...defaultSchema.attributes,
    code: [...(defaultSchema.attributes?.code ?? []), "className"],
    span: [...(defaultSchema.attributes?.span ?? []), "className"],
    pre: [...(defaultSchema.attributes?.pre ?? []), "className"],
  },
};
