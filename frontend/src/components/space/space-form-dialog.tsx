import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useCreateSpace, useUpdateSpace } from "@/hooks/use-spaces";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import type { Space } from "@/lib/types";

interface SpaceFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** 有值 = 编辑；null / undefined = 创建。 */
  space?: Space | null;
}

interface SpaceFormContentProps {
  space?: Space | null;
  onClose: () => void;
}

const STATUS_OPTIONS = [
  { value: 1, label: "已启用" },
  { value: 0, label: "未启用" },
] as const;

const spaceSchema = z.object({
  name: z.string().trim().min(1, "请输入空间名称").max(50, "名称不能超过 50 字"),
  description: z.string().max(200, "描述不能超过 200 字").optional(),
  status: z.number(),
});

type SpaceFormValues = z.infer<typeof spaceSchema>;

function SpaceFormContent({ space, onClose }: SpaceFormContentProps) {
  const isEdit = !!space;

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<SpaceFormValues>({
    resolver: zodResolver(spaceSchema),
    defaultValues: {
      name: space?.name ?? "",
      description: space?.description ?? "",
      status: space?.status ?? 1,
    },
  });

  const status = watch("status");

  const createSpace = useCreateSpace();
  const updateSpace = useUpdateSpace();

  const onSubmit = handleSubmit((values) => {
    if (isEdit && space) {
      updateSpace.mutate(
        { id: space.id, payload: values },
        { onSuccess: () => onClose() }
      );
    } else {
      // 创建时不带 status，保持后端默认
      const createPayload = {
        name: values.name,
        description: values.description,
      };
      createSpace.mutate(createPayload, { onSuccess: () => onClose() });
    }
  });

  const isPending = createSpace.isPending || updateSpace.isPending;
  const errorMessage = createSpace.error?.message || updateSpace.error?.message;

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="space-y-2">
        <label htmlFor="space-name" className="text-sm font-medium">
          名称 <span className="text-destructive" aria-hidden="true">*</span>
        </label>
        <Input
          id="space-name"
          placeholder="我的 API 空间"
          aria-invalid={!!errors.name}
          aria-describedby={errors.name ? "space-name-error" : undefined}
          {...register("name")}
        />
        {errors.name && (
          <p id="space-name-error" role="alert" className="text-xs text-destructive">
            {errors.name.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <label htmlFor="space-description" className="text-sm font-medium">
          描述
        </label>
        <Input
          id="space-description"
          placeholder="可选描述"
          {...register("description")}
        />
        {errors.description && (
          <p role="alert" className="text-xs text-destructive">
            {errors.description.message}
          </p>
        )}
      </div>

      {isEdit && (
        <div className="space-y-2">
          <label htmlFor="space-status" className="text-sm font-medium">
            状态
          </label>
          <Select
            value={String(status)}
            onValueChange={(value) => setValue("status", Number(value), { shouldValidate: true })}
          >
            <SelectTrigger id="space-status">
              <SelectValue placeholder="选择状态" />
            </SelectTrigger>
            <SelectContent>
              {STATUS_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={String(opt.value)}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {errorMessage && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage}
        </p>
      )}

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          取消
        </Button>
        <Button type="submit" disabled={isPending}>
          {isPending ? (isEdit ? "更新中…" : "创建中…") : isEdit ? "更新" : "创建"}
        </Button>
      </DialogFooter>
    </form>
  );
}

/** 空间表单弹窗：创建 / 编辑二合一。 */
export function SpaceFormDialog({ open, onOpenChange, space }: SpaceFormDialogProps) {
  const isEdit = !!space;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{isEdit ? "编辑空间" : "创建空间"}</DialogTitle>
          <DialogDescription>
            {isEdit ? "更新空间信息。" : "添加一个新的 API 空间以开始测试。"}
          </DialogDescription>
        </DialogHeader>
        {open && (
          <SpaceFormContent
            key={space?.id ?? "new"}
            space={space}
            onClose={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
