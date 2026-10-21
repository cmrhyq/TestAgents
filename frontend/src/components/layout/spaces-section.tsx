import { useState } from "react";
import * as AccordionPrimitive from "@radix-ui/react-accordion";
import { useNavigate } from "react-router-dom";
import { ChevronDown, Folder, PlusCircle, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { useSpaces } from "@/hooks/use-spaces";
import {
  useConversations,
  useUpdateConversation,
  useDeleteConversation,
} from "@/hooks/use-conversations";
import { formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Accordion, AccordionContent, AccordionItem } from "@/components/ui/accordion";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ConfirmDeleteDialog } from "@/components/shared/confirm-delete-dialog";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import type { Conversation } from "@/lib/types";

function SpacesSkeleton() {
  return (
    <div className="space-y-2 px-3 py-2">
      {[1, 2, 3].map((i) => (
        <div key={i} className="h-7 animate-pulse rounded-md bg-muted" />
      ))}
    </div>
  );
}

interface RenameDialogProps {
  conversation: Conversation | null;
  onOpenChange: (open: boolean) => void;
  onSubmit: (title: string) => void;
}

function RenameDialog({ conversation, onOpenChange, onSubmit }: RenameDialogProps) {
  const [value, setValue] = useState("");

  return (
    <Dialog
      open={conversation !== null}
      onOpenChange={(open) => {
        if (!open) onOpenChange(false);
        else setValue(conversation?.title ?? "");
      }}
    >
      <DialogContent
        className="max-w-sm"
        onOpenAutoFocus={() => setValue(conversation?.title ?? "")}
      >
        <DialogHeader>
          <DialogTitle>重命名会话</DialogTitle>
        </DialogHeader>
        <Input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="输入会话标题"
          onKeyDown={(e) => {
            if (e.key === "Enter" && value.trim()) {
              onSubmit(value.trim());
            }
          }}
        />
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button disabled={!value.trim()} onClick={() => onSubmit(value.trim())}>
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface SpaceAccordionItemProps {
  spaceId: string | number;
  spaceName: string;
}

function SpaceAccordionItem({ spaceId, spaceName }: SpaceAccordionItemProps) {
  const navigate = useNavigate();
  const { data, isLoading } = useConversations({
    space_id: spaceId,
    status: 1,
    page_size: 100,
  });
  const updateConversation = useUpdateConversation();
  const deleteConversation = useDeleteConversation();

  const [renameTarget, setRenameTarget] = useState<Conversation | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Conversation | null>(null);

  const conversations = data?.items ?? [];

  const handleNewConversation = () => {
    navigate(`/workflows/chat?space_id=${spaceId}`);
  };

  const handleOpen = (id: string | number) => {
    navigate(`/workflows/chat?conversation_id=${id}`);
  };

  return (
    <AccordionItem value={String(spaceId)} className="border-none">
      <AccordionPrimitive.Header className="flex">
        <AccordionPrimitive.Trigger
          className={cn(
            "group flex flex-1 items-center gap-1 rounded-md px-2 py-1.5 text-sm font-medium transition-colors hover:bg-muted hover:no-underline [&[data-state=open]_.space-chevron]:rotate-180"
          )}
        >
          <Folder className="h-4 w-4 shrink-0 text-muted-foreground" />
          <span className="min-w-0 flex-1 truncate text-left text-foreground">{spaceName}</span>
          <ChevronDown className="space-chevron h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform duration-200" />
          <span
            className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              aria-label="新建对话"
              className="rounded p-0.5 text-muted-foreground hover:bg-background hover:text-foreground"
              onClick={(e) => {
                e.stopPropagation();
                handleNewConversation();
              }}
            >
              <PlusCircle className="h-3.5 w-3.5" />
            </button>
          </span>
        </AccordionPrimitive.Trigger>
      </AccordionPrimitive.Header>
      <AccordionContent className="pb-1 pt-0">
        {isLoading ? (
          <div className="space-y-1 pl-6 pr-2 py-1">
            {[1, 2].map((i) => (
              <div key={i} className="h-6 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : conversations.length === 0 ? (
          <p className="pl-6 pr-2 py-1 text-xs text-muted-foreground">暂无会话</p>
        ) : (
          <ul className="space-y-0.5 pl-6">
            {conversations.map((item) => (
              <li key={item.id} className="group/item">
                <div className="flex w-full items-center gap-2 rounded-md px-2 py-1 text-sm text-foreground/80 transition-colors hover:bg-muted hover:text-foreground">
                  <button
                    type="button"
                    className="min-w-0 flex-1 truncate text-left"
                    onClick={() => handleOpen(item.id)}
                  >
                    {item.title || "未命名会话"}
                  </button>
                  <span className="shrink-0 text-xs text-muted-foreground group-hover/item:hidden">
                    {formatRelativeTime(item.last_message_at || item.updated_at)}
                  </span>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button
                          type="button"
                          aria-label="会话操作"
                          className="invisible shrink-0 rounded p-0.5 text-muted-foreground group-hover/item:visible hover:bg-background hover:text-foreground focus-visible:visible"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <MoreHorizontal className="h-3.5 w-3.5" />
                        </button>
                      </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="shadow-popover">
                      <DropdownMenuItem onClick={() => setRenameTarget(item)}>
                        <Pencil className="h-3.5 w-3.5" />
                        重命名
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={() => setDeleteTarget(item)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        删除
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </li>
            ))}
          </ul>
        )}
      </AccordionContent>

      <RenameDialog
        conversation={renameTarget}
        onOpenChange={() => setRenameTarget(null)}
        onSubmit={(title) => {
          if (renameTarget) {
            updateConversation.mutate({ id: renameTarget.id, payload: { title } });
          }
          setRenameTarget(null);
        }}
      />

      <ConfirmDeleteDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        onConfirm={() => {
          if (deleteTarget) {
            deleteConversation.mutate(deleteTarget.id);
            setDeleteTarget(null);
          }
        }}
        title="删除会话"
        description={
          <span>
            确定要删除会话 <strong>{deleteTarget?.title || "未命名会话"}</strong>{" "}
            吗？该会话的所有消息将被永久删除。
          </span>
        }
        confirmText="删除会话"
      />
    </AccordionItem>
  );
}

export function SpacesSection() {
  const [sectionOpen, setSectionOpen] = useState(true);
  const { data, isLoading, isError } = useSpaces({ page_size: 100, status: 1 });

  const spaces = data?.items ?? [];
  const total = data?.total ?? spaces.length;

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <button
        type="button"
        className="flex w-full shrink-0 items-center gap-1 px-5 py-3 text-left"
        onClick={() => setSectionOpen((open) => !open)}
        aria-expanded={sectionOpen}
      >
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform duration-200",
            !sectionOpen && "-rotate-90"
          )}
        />
        <span className="text-[11px] font-medium text-muted-foreground">空间 ({total})</span>
      </button>

      {sectionOpen && (
        <div className="spaces-scroll min-h-0 flex-1 px-3 pb-4">
          {isLoading && <SpacesSkeleton />}

          {isError && <p className="px-2 py-2 text-xs text-destructive">加载空间列表失败</p>}

          {!isLoading && !isError && spaces.length === 0 && (
            <p className="px-2 py-2 text-xs text-muted-foreground">
              暂无空间，请先在仪表盘创建空间
            </p>
          )}

          {!isLoading && !isError && spaces.length > 0 && (
            <Accordion type="multiple" className="space-y-0.5">
              {spaces.map((space) => (
                <SpaceAccordionItem
                  key={space.id}
                  spaceId={space.id}
                  spaceName={space.name}
                />
              ))}
            </Accordion>
          )}
        </div>
      )}
    </div>
  );
}
