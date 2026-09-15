import { AlertCircle, RotateCcw } from "lucide-react";
import { Button } from "@nous-research/ui/ui/components/button";
import { Card } from "@nous-research/ui/ui/components/card";

import { cn } from "@/lib/utils";

interface LoadErrorNoticeProps {
  /** What failed to load, e.g. "cron jobs". */
  what: string;
  /** The humanized error (`errorMessage(err)`), shown as a dimmed detail line. */
  detail?: string | null;
  onRetry: () => void;
  className?: string;
}

/**
 * Persistent "could not load X" card with a Retry button. Used instead of an
 * error toast for page loaders: a toast vanishes after 3s and cannot carry a
 * retry action, so the user was left with an empty page and no next step.
 */
export function LoadErrorNotice({ what, detail, onRetry, className }: LoadErrorNoticeProps) {
  return (
    <Card
      role="alert"
      className={cn(
        "flex items-start gap-2 border-destructive/40 bg-destructive/5 px-3 py-2 text-xs",
        className,
      )}
    >
      <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-destructive" />
      <div className="min-w-0 flex-1">
        <div className="text-destructive">
          Could not load {what}. Check that the dashboard server is running and click Retry.
        </div>
        {detail && <div className="mt-0.5 text-muted-foreground">Details: {detail}</div>}
        <Button
          size="sm"
          outlined
          className="mt-1"
          onClick={onRetry}
          prefix={<RotateCcw className="h-3.5 w-3.5" />}
        >
          Retry
        </Button>
      </div>
    </Card>
  );
}
