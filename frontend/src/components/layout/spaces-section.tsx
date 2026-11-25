import { useState } from "react";
import * as AccordionPrimitive from "@radix-ui/react-accordion";
import { useLocation, useNavigate } from "react-router-dom";
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
  const location = useLocation();
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

  // 当前路由处于本空间的对话页时，从 URL 解析出正在查看的会话，用于高亮与删除跳转判断
  const chatMatch = location.pathname.match(/^\/spaces\/([^/]+)\/chat$/);
  const isSpaceChat = chatMatch?.[1] === String(spaceId);
  const activeConversationId = isSpaceChat
    ? new URLSearchParams(location.search).get("conversation_id")
    : null;
  const isNewChatState = isSpaceChat && !activeConversationId;

  const handleNewConversation = () => {
    navigate(`/spaces/${spaceId}/chat`);
  };

  const handleOpen = (id: string | number) => {
    navigate(`/spaces/${spaceId}/chat?conversation_id=${id}`);
  };

  return (
    <AccordionItem value={String(spaceId)} className="border-none">
      {/* 折叠与新建是两个并列按钮，不再相互嵌套；focus-within 保证键盘用户也能看到新建入口 */}
      <AccordionPrimitive.Header asChild>
        <div className="group relative flex items-center rounded-md text-[13px] leading-5 transition-colors hover:bg-hover focus-within:bg-hover">
          <AccordionPrimitive.Trigger
            className={cn(
              "flex min-w-0 flex-1 items-center gap-1.5 py-1.5 pl-2 pr-[76px] text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 [&[data-state=open]_.space-chevron]:rotate-180"
            )}
          >
            <Folder className="h-4 w-4 shrink-0 text-muted-foreground" strokeWidth={1.75} />
            <span className="min-w-0 flex-1 truncate font-medium text-foreground">
              {spaceName}
            </span>
            <ChevronDown className="space-chevron h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform duration-200" />
          </AccordionPrimitive.Trigger>
          <button
            type="button"
            aria-label="新建对话"
            title="新建对话"
            className={cn(
              "absolute right-[52px] top-1/2 flex h-5 w-5 -translate-y-1/2 items-center justify-center rounded opacity-0 transition-opacity",
              "group-hover:opacity-100 group-focus-within:opacity-100 focus-visible:opacity-100",
              isNewChatState
                ? "bg-selected text-foreground"
                : "text-muted-foreground hover:bg-hover-strong hover:text-foreground"
            )}
            onClick={handleNewConversation}
          >
            <PlusCircle className="h-3.5 w-3.5" />
          </button>
        </div>
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
                <div
                  className={cn(
                    "flex w-full items-center gap-2 rounded-md px-2 py-1 text-[13px] leading-5 transition-colors",
                    String(item.id) === activeConversationId
                      ? "bg-selected font-medium text-foreground"
                      : "text-muted-foreground hover:bg-hover hover:text-foreground"
                  )}
                >
                  <button
                    type="button"
                    className="min-w-0 flex-1 truncate text-left"
                    onClick={() => handleOpen(item.id)}
                  >
                    {item.title || "未命名会话"}
                  </button>
                  <span className="shrink-0 text-[11px] text-muted-foreground group-hover/item:hidden">
                    {formatRelativeTime(item.last_message_at || item.updated_at)}
                  </span>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button
                        type="button"
                        aria-label="会话操作"
                        className="invisible flex h-5 w-5 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-hover-strong hover:text-foreground focus-visible:visible group-hover/item:visible"
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
            const wasActive = String(deleteTarget.id) === activeConversationId;
            deleteConversation.mutate(deleteTarget.id, {
              // 删除的是正在查看的会话时，主动跳回该空间的新建态，避免停在失效会话上
              onSettled: () => {
                if (wasActive) navigate(`/spaces/${spaceId}/chat`);
              },
            });
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

/** 侧边栏的空间区块：按空间折叠列出会话，支持重命名与删除。 */
export function SpacesSection() {
  const [sectionOpen, setSectionOpen] = useState(true);
  const { data, isLoading, isError } = useSpaces({ page_size: 100, status: 1 });

  const spaces = data?.items ?? [];
  const total = data?.total ?? spaces.length;

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <button
        type="button"
        className="flex w-full shrink-0 items-center gap-1.5 px-2.5 pb-1 pt-2 text-left"
        onClick={() => setSectionOpen((open) => !open)}
        aria-expanded={sectionOpen}
      >
        <ChevronDown
          className={cn(
            "h-3 w-3 shrink-0 text-muted-foreground transition-transform duration-200",
            !sectionOpen && "-rotate-90"
          )}
        />
        <span className="text-[11px] font-medium leading-4 text-muted-foreground">
          空间会话 ({total})
        </span>
      </button>

      {sectionOpen && (
        <div className="spaces-scroll min-h-0 flex-1 px-2.5 pb-3">
          {isLoading && <SpacesSkeleton />}

          {isError && (
            <p className="px-2 py-2 text-[12px] text-destructive">加载空间列表失败</p>
          )}

          {!isLoading && !isError && spaces.length === 0 && (
            <p className="px-2 py-2 text-[12px] leading-4 text-muted-foreground">
              暂无空间，先在「测试空间」创建一个
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
