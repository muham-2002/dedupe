import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useState } from "react";

interface FileNameDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (fileName: string) => void;
  defaultFileName?: string;
}

export function FileNameDialog({
  isOpen,
  onClose,
  onConfirm,
  defaultFileName = "duplicate_groups"
}: FileNameDialogProps) {
  const [fileName, setFileName] = useState(defaultFileName);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const finalFileName = fileName.endsWith('.csv') ? fileName : `${fileName}.csv`;
    onConfirm(finalFileName);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[425px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Save File</DialogTitle>
            <DialogDescription>
              Enter a name for your CSV file
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <Input
              value={fileName}
              onChange={(e) => setFileName(e.target.value)}
              placeholder="Enter file name"
              className="col-span-3"
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={!fileName.trim()}>
              Download
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
} 