"use client";
import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Card, CardContent } from "@/components/ui/card";
import { Upload, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import toast from "react-hot-toast";

interface FileUploadProps {
  onFileUpload: (files: File[]) => void;
  handleClearAll: () => void;
  files: File[];
  isLoading: boolean;
  maxFiles?: number;
}

export default function FileUpload({
  onFileUpload,
  handleClearAll,
  files,
  isLoading,
  maxFiles = 1,
}: FileUploadProps) {
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        // Check if files have different extensions
        const extensions = acceptedFiles.map(file => file.name.split('.').pop()?.toLowerCase());
        const uniqueExtensions = new Set(extensions);
        
        if (uniqueExtensions.size > 1) {
          toast.error("All files must have the same extension");
          return;
        }

        onFileUpload(acceptedFiles);
      }
    },
    [onFileUpload]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [
        ".xlsx",
      ],
      "text/csv": [".csv"],
    },
    multiple: true,
    maxFiles: maxFiles,
  });

  return (
    <div className="flex justify-center h-full">
      <Card
        {...getRootProps()}
        className={`w-full cursor-pointer transition-all duration-300 hover:border-primary/50 hover:bg-accent h-full ${
          isDragActive ? "border-primary border-2 bg-accent" : "border-dashed"
        }`}
      >
        <CardContent className="flex flex-col items-center justify-center space-y-4 p-6 h-full">
          <input {...getInputProps()} disabled={isLoading} />
          <div className="rounded-full bg-primary/10 p-4">
            <Upload className="h-8 w-8 text-primary" />
          </div>
          {files.length > 0 ? (
            <div className="text-center">
              <div className="flex flex-row mb-2">
                {files.map((file, index) => (
                  <Badge variant="secondary" key={index}>
                    {file.name}
                  </Badge>
                ))}
              </div>
              <Button
                variant="ghost"
                size="sm"
                disabled={isLoading}
                className="text-red-500 hover:bg-red-100 hover:text-red-600"
                onClick={(e) => {
                  e.stopPropagation();
                  handleClearAll();
                }}
              >
                <X className="mr-1 h-4 w-4" />
                Remove All
              </Button>
            </div>
          ) : (
            <div className="text-center space-y-2">
              <p className="font-medium">
                Drop your {maxFiles > 1 ? "files" : "file"} here or{" "}
                <span className="text-primary">browse</span>
              </p>
              <p className="text-sm text-muted-foreground">
                Supports CSV & XLSX files{" "}
                {maxFiles > 1 ? `(Max ${maxFiles} files)` : ""}
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
