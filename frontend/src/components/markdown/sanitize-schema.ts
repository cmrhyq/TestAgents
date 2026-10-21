import { defaultSchema, type Options as SanitizeSchema } from "rehype-sanitize";

/**
 * rehype-sanitize schema：在 GitHub 默认白名单基础上，仅扩展代码高亮所需属性。
 * 禁止 raw HTML、脚本、事件处理器；img 不在 tagNames 中（不渲染远程图片）。
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
