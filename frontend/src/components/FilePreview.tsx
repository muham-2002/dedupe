import { useState, useEffect } from 'react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import * as XLSX from 'xlsx'
import Papa from 'papaparse'
import { Loader2 } from 'lucide-react'

// Add type for Papa.parse results
interface ParseResult {
  data: Record<string, unknown>[];
  errors: Papa.ParseError[];
  meta: Papa.ParseMeta;
}

interface FilePreviewProps {
  file: File | null
  setAvailableColumns: (columns: string[]) => void
}

export default function FilePreview({ file, setAvailableColumns }: FilePreviewProps) {
  const [previewData, setPreviewData] = useState<{ headers: string[]; rows: any[] } | null>(null)
  const [totalRows, setTotalRows] = useState<number>(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!file) {
      setPreviewData(null)
      setTotalRows(0)
      setError(null)
      return
    }

    const readFile = async () => {
      setLoading(true)
      setError(null)
      try {
        if (file.name.endsWith('.csv')) {
          // Handle CSV files
          const text = await file.text()
          Papa.parse(text, {
            header: true,
            complete: (results: ParseResult) => {
              if (results.data && results.data.length > 0) {
                const firstRow = results.data[0] as Record<string, unknown>;
                setPreviewData({
                  headers: Object.keys(firstRow),
                  rows: results.data.slice(0, 10)
                })
                setTotalRows(results.data.length)
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
            const rows = data.slice(1, 11).map(row => {
              const rowData: Record<string, any> = {}
              headers.forEach((header, index) => {
                rowData[header] = (row as any[])[index]
              })
              return rowData
            })

            setPreviewData({ headers, rows })
            setAvailableColumns(headers)
            setTotalRows(data.length - 1) // Subtract 1 to exclude header row
          }
        } else {
          throw new Error('Unsupported file format. Please upload a CSV or Excel file.')
        }
      } catch (error) {
        console.error('Error reading file:', error)
        setError(error instanceof Error ? error.message : 'Error reading file')
        setPreviewData(null)
        setAvailableColumns([])
        setTotalRows(0)
      } finally {
        setLoading(false)
      }
    }

    readFile()
  }, [file])

  return (
    <Card className="border-none shadow-md">
      <CardHeader className="pb-4">
        <CardTitle className="text-xl font-semibold flex items-center gap-2">
          Preview
          {file && !error && (
            <span className="text-sm text-muted-foreground">
              - {file.name} • {totalRows.toLocaleString()} rows
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center justify-center h-[300px] rounded-lg border-2 border-dashed border-muted">
            <div className="text-center space-y-2">
              <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto" />
              <p className="text-sm text-muted-foreground">Loading preview...</p>
            </div>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-[300px] rounded-lg border-2 border-dashed border-destructive/20 bg-destructive/5">
            <div className="text-center space-y-2 px-4">
              <p className="text-sm font-medium text-destructive">{error}</p>
              <p className="text-sm text-muted-foreground">Please try uploading a different file</p>
            </div>
          </div>
        ) : !file ? (
          <div className="flex items-center justify-center h-[300px] rounded-lg border-2 border-dashed border-muted">
            <div className="text-center space-y-2">
              <p className="text-lg font-medium text-muted-foreground">No file selected</p>
              <p className="text-sm text-muted-foreground">Upload a file to see preview</p>
            </div>
          </div>
        ) : (
          <div className="rounded-lg border overflow-hidden">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent bg-muted/50">
                    {previewData?.headers.map((header) => (
                      <TableHead key={header} className="text-xs font-medium whitespace-nowrap">
                        {header}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {previewData?.rows.map((row, index) => (
                    <TableRow key={index} className="hover:bg-accent">
                      {previewData.headers.map((header) => (
                        <TableCell 
                          key={`${index}-${header}`} 
                          className="text-xs py-2 whitespace-nowrap"
                        >
                          {row[header] ?? '-'}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
