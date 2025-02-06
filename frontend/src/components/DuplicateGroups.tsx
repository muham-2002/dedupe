import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { CheckCircle2, X } from 'lucide-react'

interface DuplicateGroupProps {
  group: {
    cluster_id: number
    group_size: number
    confidence_score: number
    records: any[]
  }
  onSelectRow: (clusterId: number, rowIndex: number, record: any, isSelected: boolean) => void
  columnWidths: Record<string, number>
  selectedRows: number[]
  onSelectAllDuplicates?: () => void
}

export default function DuplicateGroup({ group, onSelectRow, columnWidths, selectedRows, onSelectAllDuplicates }: DuplicateGroupProps) {
  const handleSelectRow = (rowIndex: number, record: any) => {
    const isSelected = selectedRows.includes(rowIndex)
    onSelectRow(group.cluster_id, rowIndex, record, !isSelected)
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader className="bg-gray-100">
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span>Duplicate Group {group.cluster_id + 1}</span>
            <Badge variant="secondary">
              Confidence: {(group.confidence_score * 100).toFixed(2)}%
            </Badge>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead style={{ width: '100px', minWidth: '100px' }}>Action</TableHead>
                {Object.keys(group.records[0])
                  .filter(key => !['confidence_score', 'source_file'].includes(key))
                  .map((key) => (
                    <TableHead
                      key={key}
                      className="whitespace-nowrap font-bold"
                      style={{ width: `${columnWidths[key] * 8}px`, minWidth: `${columnWidths[key] * 8}px` }}
                    >
                      {key}
                    </TableHead>
                  ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {group.records.map((record, index) => (
                <TableRow
                  key={index}
                  className={selectedRows.includes(index) ? 'bg-red-50' : ''}
                >
                  <TableCell style={{ width: '100px', minWidth: '100px' }}>
                    <Button
                      onClick={() => handleSelectRow(index, record)}
                      variant={selectedRows.includes(index) ? 'default' : 'outline'}
                      size="sm"
                      className={`w-24 ${selectedRows.includes(index)
                        ? 'bg-red-500 hover:bg-red-600 text-white'
                        : 'text-red-500 hover:bg-red-50 border-red-500'
                        }`}
                    >
                      {selectedRows.includes(index) ? (
                        <>
                          <X className="mr-1 h-4 w-4" /> Removed
                        </>
                      ) : (
                        <>
                          <X className="mr-1 h-4 w-4" /> Remove
                        </>
                      )}
                    </Button>
                  </TableCell>
                  {Object.entries(record)
                    .filter(([key]) => !['confidence_score', 'source_file'].includes(key))
                    .map(([key, value], valueIndex) => (
                      <TableCell
                        key={valueIndex}
                        className="whitespace-nowrap"
                        style={{ width: `${columnWidths[key] * 8}px`, minWidth: `${columnWidths[key] * 8}px` }}
                      >
                        {String(value)}
                      </TableCell>
                    ))}

                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  )
}
