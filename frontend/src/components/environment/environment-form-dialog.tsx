import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useCreateEnvironment, useUpdateEnvironment } from "@/hooks/use-environments";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { isValidJson } from "@/lib/form-utils";
import type { Environment } from "@/lib/types";

interface EnvironmentFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  spaceId: string | number;
  environment?: Environment | null;
}

interface EnvironmentFormContentProps {
  spaceId: string | number;
  environment?: Environment | null;
  onClose: () => void;
}

const environmentSchema = z.object({
  name: z.string().trim().min(1, "请输入环境名称").max(50, "名称不能超过 50 字"),
  base_url: z.string().trim().min(1, "请输入基础 URL").url("请输入有效的 URL，如 https://api.example.com"),
  description: z.string().max(200, "描述不能超过 200 字").optional(),
  variables: z.string().refine(isValidJson, "变量必须是合法 JSON"),
  is_default: z.boolean(),
});

type EnvironmentFormValues = z.infer<typeof environmentSchema>;

function EnvironmentFormContent({ spaceId, environment, onClose }: EnvironmentFormContentProps) {
  const isEdit = !!environment;

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<EnvironmentFormValues>({
    resolver: zodResolver(environmentSchema),
    defaultValues: {
      name: environment?.name ?? "",
      base_url: environment?.base_url ?? "",
      description: environment?.description ?? "",
      variables: environment?.variables ?? "",
      is_default: environment?.is_default === 1,
    },
  });

  const createEnvironment = useCreateEnvironment();
  const updateEnvironment = useUpdateEnvironment();

  const onSubmit = handleSubmit((values) => {
    const payload: Partial<Environment> = {
      space_id: spaceId,
      ...values,
      is_default: values.is_default ? 1 : 0,
    };

    if (isEdit && environment) {
      updateEnvironment.mutate({ id: environment.id, payload }, { onSuccess: () => onClose() });
    } else {
      createEnvironment.mutate(payload, {
        onSuccess: () => onClose(),
      });
    }
  });

  const isPending = createEnvironment.isPending || updateEnvironment.isPending;

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="space-y-2">
        <label htmlFor="env-name" className="text-sm font-medium">
          名称 <span className="text-destructive" aria-hidden="true">*</span>
        </label>
        <Input
          id="env-name"
          placeholder="生产环境"
          aria-invalid={!!errors.name}
          aria-describedby={errors.name ? "env-name-error" : undefined}
          {...register("name")}
        />
        {errors.name && (
          <p id="env-name-error" role="alert" className="text-xs text-destructive">
            {errors.name.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <label htmlFor="env-base-url" className="text-sm font-medium">
          基础 URL <span className="text-destructive" aria-hidden="true">*</span>
        </label>
        <Input
          id="env-base-url"
          placeholder="https://api.example.com"
          aria-invalid={!!errors.base_url}
          aria-describedby={errors.base_url ? "env-base-url-error" : undefined}
          {...register("base_url")}
        />
        {errors.base_url && (
          <p id="env-base-url-error" role="alert" className="text-xs text-destructive">
            {errors.base_url.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <label htmlFor="env-description" className="text-sm font-medium">
          描述
        </label>
        <Input
          id="env-description"
          placeholder="可选描述"
          {...register("description")}
        />
        {errors.description && (
          <p role="alert" className="text-xs text-destructive">
            {errors.description.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <label htmlFor="env-variables" className="text-sm font-medium">
          变量（JSON）
        </label>
        <Textarea
          id="env-variables"
          placeholder='{"enable": "xxx", "TIMEOUT": "30"}'
          rows={3}
          className="font-mono text-xs"
          aria-invalid={!!errors.variables}
          aria-describedby={errors.variables ? "env-variables-error" : undefined}
          {...register("variables")}
        />
        {errors.variables && (
          <p id="env-variables-error" role="alert" className="text-xs text-destructive">
            {errors.variables.message}
          </p>
        )}
      </div>

      <div className="flex items-center gap-2">
        <input
          id="env-default"
          type="checkbox"
          className="h-4 w-4 rounded border-border"
          {...register("is_default")}
        />
        <label htmlFor="env-default" className="text-sm font-medium">
          设为默认环境
        </label>
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

export function EnvironmentFormDialog({
  open,
  onOpenChange,
  spaceId,
  environment,
}: EnvironmentFormDialogProps) {
  const isEdit = !!environment;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{isEdit ? "编辑环境" : "添加环境"}</DialogTitle>
          <DialogDescription>
            {isEdit ? "更新环境配置。" : "为该空间添加一个新环境。"}
          </DialogDescription>
        </DialogHeader>
        {open && (
          <EnvironmentFormContent
            key={environment?.id ?? "new"}
            spaceId={spaceId}
            environment={environment}
            onClose={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
