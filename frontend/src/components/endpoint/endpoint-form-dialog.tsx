import type { ReactNode } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useCreateEndpoint, useEndpointTags, useUpdateEndpoint } from "@/hooks/use-endpoints";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { TagInput } from "@/components/endpoint/tag-input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { isValidJson } from "@/lib/form-utils";
import { cn } from "@/lib/utils";
import type { Endpoint } from "@/lib/types";

const HTTP_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"] as const;

interface EndpointFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  spaceId: string | number;
  /** 有值时进入编辑模式，否则为新建。 */
  endpoint?: Endpoint | null;
}

interface EndpointFormContentProps {
  spaceId: string | number;
  endpoint?: Endpoint | null;
  onClose: () => void;
}

const endpointSchema = z.object({
  name: z.string().trim().min(1, "请输入接口名称").max(100, "名称不能超过 100 字"),
  method: z.string().min(1, "请选择方法"),
  path: z.string().trim().min(1, "请输入接口路径"),
  summary: z.string().max(200, "摘要不能超过 200 字").optional(),
  description: z.string().max(2000, "描述不能超过 2000 字").optional(),
  tags: z.array(z.string()),
  content_type: z.string().trim().min(1, "请输入内容类型"),
  params: z.string().refine(isValidJson, "参数必须是合法 JSON"),
  headers: z.string().refine(isValidJson, "请求头必须是合法 JSON"),
  body: z.string().refine(isValidJson, "请求体必须是合法 JSON"),
});

type EndpointFormValues = z.infer<typeof endpointSchema>;

/**
 * 统计 JSON 文本的条目数，用于页签计数。
 *
 * 容忍非法 JSON：解析失败按 0 计。用户可能正打到一半，页签计数只是提示，
 * 不该因此让弹窗渲染出错。
 */
function countEntries(raw: string | undefined): number {
  const text = (raw ?? "").trim();
  if (!text) return 0;
  try {
    const parsed: unknown = JSON.parse(text);
    if (Array.isArray(parsed)) return parsed.length;
    if (parsed !== null && typeof parsed === "object") return Object.keys(parsed).length;
    return 0;
  } catch {
    return 0;
  }
}

interface FormFieldProps {
  id: string;
  label: string;
  required?: boolean;
  error?: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}

/** 统一字段容器：标签、错误与说明共用一套间距，避免各字段间距不一。 */
function FormField({ id, label, required, error, hint, children, className }: FormFieldProps) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <label htmlFor={id} className="flex items-baseline gap-1 text-sm font-medium">
        {label}
        {required && (
          <span className="text-destructive" aria-hidden="true">
            *
          </span>
        )}
      </label>
      {children}
      {error ? (
        <p id={`${id}-error`} role="alert" className="text-xs text-destructive">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-[11px] text-muted-foreground">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

/** 页签标题：附带条目计数与错误标记，收起状态下也能看出哪里有问题。 */
function TabLabel({ text, count, invalid }: { text: string; count?: number; invalid?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      {text}
      {count !== undefined && count > 0 && (
        <span className="font-mono text-[10px] text-muted-foreground">{count}</span>
      )}
      {invalid && (
        <span
          className="inline-block h-1.5 w-1.5 rounded-full bg-destructive"
          aria-label="有错误"
        />
      )}
    </span>
  );
}

function EndpointFormContent({ spaceId, endpoint, onClose }: EndpointFormContentProps) {
  const isEdit = !!endpoint;

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<EndpointFormValues>({
    resolver: zodResolver(endpointSchema),
    defaultValues: {
      name: endpoint?.name ?? "",
      method: endpoint?.method ?? "GET",
      path: endpoint?.path ?? "",
      summary: endpoint?.summary ?? "",
      description: endpoint?.description ?? "",
      tags: endpoint?.tags ?? [],
      content_type: endpoint?.content_type ?? "application/json",
      params: endpoint?.params ?? "",
      headers: endpoint?.headers ?? "",
      body: endpoint?.body ?? "",
    },
  });

  const method = watch("method");
  const tags = watch("tags") ?? [];
  const paramsText = watch("params");
  const headersText = watch("headers");

  // 复用列表页已缓存的标签聚合，避免弹窗再发一次请求
  const { data: tagFacets = [] } = useEndpointTags(spaceId);

  const createEndpoint = useCreateEndpoint();
  const updateEndpoint = useUpdateEndpoint();

  const onSubmit = handleSubmit((values) => {
    const payload: Partial<Endpoint> = {
      space_id: spaceId,
      ...values,
      operation_id: values.name.toLowerCase().replace(/\s+/g, "_"),
    };

    if (isEdit && endpoint) {
      updateEndpoint.mutate({ id: endpoint.id, payload }, { onSuccess: () => onClose() });
    } else {
      createEndpoint.mutate(payload, {
        onSuccess: () => onClose(),
      });
    }
  });

  const isPending = createEndpoint.isPending || updateEndpoint.isPending;
  const hasErrors = Object.keys(errors).length > 0;

  return (
    <form onSubmit={onSubmit} className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-6 py-5">
        {/* 基本信息：名称独占一行，方法与路径并排，改动的影响面一眼可见 */}
        <section className="space-y-4">
          <FormField id="ep-name" label="名称" required error={errors.name?.message}>
            <Input
              id="ep-name"
              placeholder="获取用户列表"
              aria-invalid={!!errors.name}
              {...register("name")}
            />
          </FormField>

          <div className="grid grid-cols-[132px_minmax(0,1fr)] gap-3">
            <FormField id="ep-method" label="方法">
              <Select
                value={method}
                onValueChange={(value) => setValue("method", value, { shouldValidate: true })}
              >
                <SelectTrigger id="ep-method">
                  <SelectValue placeholder="选择方法" />
                </SelectTrigger>
                <SelectContent>
                  {HTTP_METHODS.map((m) => (
                    <SelectItem key={m} value={m}>
                      {m}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>

            <FormField id="ep-path" label="路径" required error={errors.path?.message}>
              <Input
                id="ep-path"
                placeholder="/api/users"
                aria-invalid={!!errors.path}
                {...register("path")}
              />
            </FormField>
          </div>

          <FormField id="ep-summary" label="摘要" error={errors.summary?.message}>
            <Input id="ep-summary" placeholder="该接口的简要描述" {...register("summary")} />
          </FormField>

          <FormField
            id="ep-description"
            label="描述"
            error={errors.description?.message}
            hint="补充用途、约束或调用注意事项；这里的内容会进入 Agent 的接口上下文"
          >
            <Textarea
              id="ep-description"
              rows={2}
              placeholder="例如：分页接口，page 从 1 开始，单页最多 100 条"
              className="text-xs"
              {...register("description")}
            />
          </FormField>
        </section>

        <section className="space-y-2">
          <div className="flex items-baseline justify-between gap-2">
            <label htmlFor="ep-tags" className="text-sm font-medium">
              标签
            </label>
            <span className="text-[11px] text-muted-foreground">最多 10 个，用于分类与筛选</span>
          </div>
          <TagInput
            id="ep-tags"
            value={tags}
            onChange={(next) => setValue("tags", next, { shouldValidate: true })}
            suggestions={tagFacets.map((facet) => facet.name)}
          />
        </section>

        {/* 请求配置：三块内容分页签，避免长表单一路向下堆叠 */}
        <section className="space-y-3">
          <Tabs defaultValue="params" className="space-y-3">
            <TabsList className="w-full">
              <TabsTrigger value="params">
                <TabLabel text="参数" count={countEntries(paramsText)} invalid={!!errors.params} />
              </TabsTrigger>
              <TabsTrigger value="headers">
                <TabLabel
                  text="请求头"
                  count={countEntries(headersText)}
                  invalid={!!errors.headers}
                />
              </TabsTrigger>
              <TabsTrigger value="body">
                <TabLabel text="请求体" invalid={!!errors.body || !!errors.content_type} />
              </TabsTrigger>
            </TabsList>

            <TabsContent value="params" className="min-h-[220px] space-y-1.5">
              <Textarea
                id="ep-params"
                placeholder='[{"name": "id", "in": "path", "type": "integer", "required": true}]'
                rows={8}
                className="font-mono text-xs"
                aria-invalid={!!errors.params}
                aria-label="参数定义 JSON"
                {...register("params")}
              />
              {errors.params ? (
                <p role="alert" className="text-xs text-destructive">
                  {errors.params.message}
                </p>
              ) : (
                <p className="text-[11px] text-muted-foreground">
                  JSON 数组，每项含 name / in / type / required / default / description
                </p>
              )}
            </TabsContent>

            <TabsContent value="headers" className="min-h-[220px] space-y-1.5">
              <Textarea
                id="ep-headers"
                placeholder='[{"name": "Authorization", "in": "header", "type": "string", "required": true}]'
                rows={8}
                className="font-mono text-xs"
                aria-invalid={!!errors.headers}
                aria-label="请求头定义 JSON"
                {...register("headers")}
              />
              {errors.headers ? (
                <p role="alert" className="text-xs text-destructive">
                  {errors.headers.message}
                </p>
              ) : (
                <p className="text-[11px] text-muted-foreground">
                  OpenAPI 导入时与参数中的 header 项同源，两处保持一致
                </p>
              )}
            </TabsContent>

            <TabsContent value="body" className="min-h-[220px] space-y-3">
              <FormField
                id="ep-content-type"
                label="内容类型"
                error={errors.content_type?.message}
                hint="与下方请求体的 media type 对应"
              >
                <Input
                  id="ep-content-type"
                  placeholder="application/json"
                  aria-invalid={!!errors.content_type}
                  {...register("content_type")}
                />
              </FormField>

              <Textarea
                id="ep-body"
                placeholder='{"type": "object", "properties": {...}}'
                rows={6}
                className="font-mono text-xs"
                aria-invalid={!!errors.body}
                aria-label="请求体定义 JSON"
                {...register("body")}
              />
              {errors.body && (
                <p role="alert" className="text-xs text-destructive">
                  {errors.body.message}
                </p>
              )}
            </TabsContent>
          </Tabs>
        </section>
      </div>

      <DialogFooter className="shrink-0 items-center gap-2 border-t border-border px-6 py-3 sm:space-x-0">
        {hasErrors && (
          <p className="mr-auto text-xs text-destructive">
            有未完成或格式错误的字段，请检查各页签
          </p>
        )}
        <Button type="button" variant="outline" onClick={onClose}>
          取消
        </Button>
        <Button type="submit" disabled={isPending}>
          {isPending ? "保存中…" : isEdit ? "更新" : "创建"}
        </Button>
      </DialogFooter>
    </form>
  );
}

/** 接口表单弹窗：新建与编辑复用，提交成功后关闭。 */
export function EndpointFormDialog({
  open,
  onOpenChange,
  spaceId,
  endpoint,
}: EndpointFormDialogProps) {
  const isEdit = !!endpoint;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[85vh] flex-col gap-0 overflow-hidden p-0 sm:max-w-3xl">
        <DialogHeader className="shrink-0 border-b border-border px-6 py-4">
          <DialogTitle>{isEdit ? "编辑接口" : "添加接口"}</DialogTitle>
          <DialogDescription>
            {isEdit ? "更新接口详情与请求配置。" : "为该空间添加一个新的 API 接口。"}
          </DialogDescription>
        </DialogHeader>
        {open && (
          <EndpointFormContent
            key={endpoint?.id ?? "new"}
            spaceId={spaceId}
            endpoint={endpoint}
            onClose={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
