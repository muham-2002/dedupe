'use client'
import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Card, CardContent } from '@/components/ui/card'
import { Upload, X } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface FileUploadProps {
  onFileUpload: (file: File) => void
  handleClearAll: () => void
  file: File | null
  isLoading: boolean
}

export default function FileUpload({ onFileUpload, handleClearAll, file, isLoading }: FileUploadProps) {

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        const file = acceptedFiles[0]
        onFileUpload(file)
      }
    },
    [onFileUpload]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'text/csv': ['.csv'],
    },
    multiple: false,
  })

  const removeFile = () => {
    onFileUpload(null as any)
  }

  return (
    <div className="flex justify-center h-full">
      <Card
        {...getRootProps()}
        className={`w-full cursor-pointer transition-all duration-300 hover:border-primary/50 hover:bg-accent h-full ${
          isDragActive ? 'border-primary border-2 bg-accent' : 'border-dashed'
        }`}
      >
        <CardContent className="flex flex-col items-center justify-center space-y-4 p-6 h-full">
          <input {...getInputProps()} disabled={isLoading} />
          <div className="rounded-full bg-primary/10 p-4">
            <Upload className="h-8 w-8 text-primary" />
          </div>
          {file ? (
            <div className="text-center">
              <p className="font-medium text-primary">{file.name}</p>
              <p className="text-sm text-muted-foreground">
                {(file.size / 1024 / 1024).toFixed(2)} MB
              </p>
              <Button
                variant="ghost"
                size="sm"
                disabled={isLoading}
                className="text-red-500 hover:bg-red-100 hover:text-red-600"
                onClick={(e) => {
                  handleClearAll()
                  e.stopPropagation()
                  removeFile()
                }}
              >
                <X className="mr-1 h-4 w-4" />
                Remove
              </Button>
            </div>
          ) : (
            <div className="text-center space-y-2">
              <p className="font-medium">
                Drop your file here or <span className="text-primary">browse</span>
              </p>
              <p className="text-sm text-muted-foreground">
                Supports CSV, XLS, XLSX files
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
