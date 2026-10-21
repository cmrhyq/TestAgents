import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useCreateEndpoint, useUpdateEndpoint } from "@/hooks/use-endpoints";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { isValidJson } from "@/lib/form-utils";
import type { Endpoint } from "@/lib/types";

const HTTP_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"] as const;

interface EndpointFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  spaceId: string | number;
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
  content_type: z.string().trim().min(1, "请输入内容类型"),
  params: z.string().refine(isValidJson, "参数必须是合法 JSON"),
  headers: z.string().refine(isValidJson, "请求头必须是合法 JSON"),
  body: z.string().refine(isValidJson, "请求体必须是合法 JSON"),
});

type EndpointFormValues = z.infer<typeof endpointSchema>;

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
      content_type: endpoint?.content_type ?? "application/json",
      params: endpoint?.params ?? "",
      headers: endpoint?.headers ?? "",
      body: endpoint?.body ?? "",
    },
  });

  const method = watch("method");

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

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="space-y-2">
        <label htmlFor="ep-name" className="text-sm font-medium">
          名称 <span className="text-destructive" aria-hidden="true">*</span>
        </label>
        <Input
          id="ep-name"
          placeholder="获取用户列表"
          aria-invalid={!!errors.name}
          aria-describedby={errors.name ? "ep-name-error" : undefined}
          {...register("name")}
        />
        {errors.name && (
          <p id="ep-name-error" role="alert" className="text-xs text-destructive">
            {errors.name.message}
          </p>
        )}
      </div>

      <div className="grid grid-cols-[120px_1fr] gap-3">
        <div className="space-y-2">
          <label htmlFor="ep-method" className="text-sm font-medium">
            方法
          </label>
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
        </div>
        <div className="space-y-2">
          <label htmlFor="ep-path" className="text-sm font-medium">
            路径 <span className="text-destructive" aria-hidden="true">*</span>
          </label>
          <Input
            id="ep-path"
            placeholder="/api/users"
            aria-invalid={!!errors.path}
            aria-describedby={errors.path ? "ep-path-error" : undefined}
            {...register("path")}
          />
          {errors.path && (
            <p id="ep-path-error" role="alert" className="text-xs text-destructive">
              {errors.path.message}
            </p>
          )}
        </div>
      </div>

      <div className="space-y-2">
        <label htmlFor="ep-summary" className="text-sm font-medium">
          摘要
        </label>
        <Input
          id="ep-summary"
          placeholder="该接口的简要描述"
          {...register("summary")}
        />
        {errors.summary && (
          <p role="alert" className="text-xs text-destructive">
            {errors.summary.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <label htmlFor="ep-content-type" className="text-sm font-medium">
          内容类型
        </label>
        <Input
          id="ep-content-type"
          placeholder="application/json"
          {...register("content_type")}
        />
        {errors.content_type && (
          <p role="alert" className="text-xs text-destructive">
            {errors.content_type.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <label htmlFor="ep-params" className="text-sm font-medium">
          参数（JSON）
        </label>
        <Textarea
          id="ep-params"
          placeholder='[{"name": "id", "in": "path", "required": true}]'
          rows={3}
          className="font-mono text-xs"
          aria-invalid={!!errors.params}
          aria-describedby={errors.params ? "ep-params-error" : undefined}
          {...register("params")}
        />
        {errors.params && (
          <p id="ep-params-error" role="alert" className="text-xs text-destructive">
            {errors.params.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <label htmlFor="ep-headers" className="text-sm font-medium">
          请求头（JSON）
        </label>
        <Textarea
          id="ep-headers"
          placeholder='{"Authorization": "Bearer token"}'
          rows={2}
          className="font-mono text-xs"
          aria-invalid={!!errors.headers}
          aria-describedby={errors.headers ? "ep-headers-error" : undefined}
          {...register("headers")}
        />
        {errors.headers && (
          <p id="ep-headers-error" role="alert" className="text-xs text-destructive">
            {errors.headers.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <label htmlFor="ep-body" className="text-sm font-medium">
          请求体（JSON）
        </label>
        <Textarea
          id="ep-body"
          placeholder='{"type": "object", "properties": {...}}'
          rows={3}
          className="font-mono text-xs"
          aria-invalid={!!errors.body}
          aria-describedby={errors.body ? "ep-body-error" : undefined}
          {...register("body")}
        />
        {errors.body && (
          <p id="ep-body-error" role="alert" className="text-xs text-destructive">
            {errors.body.message}
          </p>
        )}
      </div>

      <DialogFooter>
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

export function EndpointFormDialog({
  open,
  onOpenChange,
  spaceId,
  endpoint,
}: EndpointFormDialogProps) {
  const isEdit = !!endpoint;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEdit ? "编辑接口" : "添加接口"}</DialogTitle>
          <DialogDescription>
            {isEdit ? "更新接口详情。" : "为该空间添加一个新的 API 接口。"}
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
