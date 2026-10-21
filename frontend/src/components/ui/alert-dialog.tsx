import type { HTMLAttributes, MouseEvent, ReactNode } from "react";
import { forwardRef, useCallback } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";

import { cn } from "@/lib/utils";

const AlertDialog = DialogPrimitive.Root;
const AlertDialogTrigger = DialogPrimitive.Trigger;
const AlertDialogPortal = DialogPrimitive.Portal;

const AlertDialogOverlay = forwardRef<HTMLDivElement, DialogPrimitive.DialogOverlayProps>(
  ({ className, ...props }, ref) => (
    <DialogPrimitive.Overlay
      ref={ref}
      className={cn(
        "fixed inset-0 z-50 bg-black/80 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
        className
      )}
      {...props}
    />
  )
);
AlertDialogOverlay.displayName = "AlertDialogOverlay";

const AlertDialogContent = forwardRef<HTMLDivElement, DialogPrimitive.DialogContentProps>(
  ({ className, children, ...props }, ref) => {
    const handlePointerDownOutside = useCallback((e: Event) => {
      e.preventDefault();
    }, []);

    return (
      <AlertDialogPortal>
        <AlertDialogOverlay />
        <DialogPrimitive.Content
          ref={ref}
          onPointerDownOutside={handlePointerDownOutside}
          onEscapeKeyDown={handlePointerDownOutside}
          className={cn(
            "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border-0 bg-background p-6 shadow-elevated duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%] sm:rounded-lg",
            className
          )}
          {...props}
        >
          {children}
        </DialogPrimitive.Content>
      </AlertDialogPortal>
    );
  }
);
AlertDialogContent.displayName = "AlertDialogContent";

function AlertDialogHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("flex flex-col space-y-2 text-center sm:text-left", className)} {...props} />
  );
}

function AlertDialogFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2", className)}
      {...props}
    />
  );
}

const AlertDialogTitle = forwardRef<HTMLHeadingElement, DialogPrimitive.DialogTitleProps>(
  ({ className, ...props }, ref) => (
    <DialogPrimitive.Title
      ref={ref}
      className={cn("text-lg font-semibold", className)}
      {...props}
    />
  )
);
AlertDialogTitle.displayName = "AlertDialogTitle";

const AlertDialogDescription = forwardRef<
  HTMLParagraphElement,
  DialogPrimitive.DialogDescriptionProps
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
));
AlertDialogDescription.displayName = "AlertDialogDescription";

interface AlertDialogActionProps extends HTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
}

const AlertDialogAction = forwardRef<HTMLButtonElement, AlertDialogActionProps>(
  ({ className, onClick, ...props }, ref) => {
    return (
      <DialogPrimitive.Close asChild>
        <button
          ref={ref}
          className={cn(
            "inline-flex h-10 items-center justify-center rounded-md bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground ring-offset-background transition-colors hover:bg-destructive/90 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
            className
          )}
          onClick={onClick as (e: MouseEvent<HTMLButtonElement>) => void}
          {...props}
        />
      </DialogPrimitive.Close>
    );
  }
);
AlertDialogAction.displayName = "AlertDialogAction";

const AlertDialogCancel = forwardRef<HTMLButtonElement, AlertDialogActionProps>(
  ({ className, ...props }, ref) => (
    <DialogPrimitive.Close asChild>
      <button
        ref={ref}
        className={cn(
          "inline-flex h-10 items-center justify-center rounded-md border-thin border-border/50 bg-background px-4 py-2 text-sm font-medium ring-offset-background transition-colors hover:bg-accent hover:text-accent-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 sm:mt-0 mt-2",
          className
        )}
        {...props}
      />
    </DialogPrimitive.Close>
  )
);
AlertDialogCancel.displayName = "AlertDialogCancel";

export {
  AlertDialog,
  AlertDialogPortal,
  AlertDialogOverlay,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
  AlertDialogCancel,
};
