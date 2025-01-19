import { useState, useEffect } from 'react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import * as XLSX from 'xlsx'
import Papa from 'papaparse'

interface FilePreviewProps {
  file: File | null
}

export default function FilePreview({ file }: FilePreviewProps) {
  const [previewData, setPreviewData] = useState<{ headers: string[]; rows: any[] } | null>(null)

  useEffect(() => {
    if (!file) {
      setPreviewData(null)
      return
    }

    const readFile = async () => {
      try {
        if (file.name.endsWith('.csv')) {
          // Handle CSV files
          const text = await file.text()
          Papa.parse(text, {
            header: true,
            preview: 10,
            complete: (results) => {
              if (results.data && results.data.length > 0) {
                const firstRow = results.data[0] as Record<string, unknown>;
                setPreviewData({
                  headers: Object.keys(firstRow),
                  rows: results.data.slice(0, 6)
                })
              }
            }
          })
        } else if (file.name.endsWith('.xlsx') || file.name.endsWith('.xls')) {
          // Handle Excel files
          const arrayBuffer = await file.arrayBuffer()
          const workbook = XLSX.read(arrayBuffer)
          const firstSheetName = workbook.SheetNames[0]
          const worksheet = workbook.Sheets[firstSheetName]
          const data = XLSX.utils.sheet_to_json(worksheet, { header: 1 })
          
          if (data && data.length > 0) {
            const headers = data[0] as string[]
            const rows = data.slice(1, 7).map(row => {
              const rowData: Record<string, any> = {}
              headers.forEach((header, index) => {
                rowData[header] = (row as any[])[index]
              })
              return rowData
            })
            
            setPreviewData({ headers, rows })
          }
        }
      } catch (error) {
        console.error('Error reading file:', error)
      }
    }

    readFile()
  }, [file])

  return (
    <Card className="border-none shadow-md">
      <CardHeader className="pb-4">
        <CardTitle className="text-xl font-semibold">Preview</CardTitle>
      </CardHeader>
      <CardContent>
        {!file ? (
          <div className="flex items-center justify-center h-[300px] rounded-lg border-2 border-dashed border-muted">
            <div className="text-center space-y-2">
              <p className="text-lg font-medium text-muted-foreground">No file selected</p>
              <p className="text-sm text-muted-foreground">Upload a file to see preview</p>
            </div>
          </div>
        ) : (
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  {previewData?.headers.map((header) => (
                    <TableHead key={header} className="text-xs font-medium">
                      {header}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {previewData?.rows.map((row, index) => (
                  <TableRow key={index} className="hover:bg-accent">
                    {previewData.headers.map((header) => (
                      <TableCell key={`${index}-${header}`} className="text-xs py-2">
                        {row[header]}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
