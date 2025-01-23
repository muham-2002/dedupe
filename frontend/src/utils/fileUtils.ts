import * as XLSX from 'xlsx'

export async function processExcelFile(file: File): Promise<any[]> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      const data = new Uint8Array(e.target?.result as ArrayBuffer)
      const workbook = XLSX.read(data, { type: 'array' })
      const sheetName = workbook.SheetNames[0]
      const worksheet = workbook.Sheets[sheetName]
      const jsonData = XLSX.utils.sheet_to_json(worksheet)
      resolve(jsonData)
    }
    reader.onerror = (error) => reject(error)
    reader.readAsArrayBuffer(file)
  })
}

export async function createDeduplicatedFile(file: File, rowsToRemove: number[]): Promise<Blob> {
  const data = await processExcelFile(file)
  const deduplicatedData = data.filter((_, index) => !rowsToRemove.includes((index)))
  
  // Handle CSV files
  if (file.name.toLowerCase().endsWith('.csv')) {
    const headers = Object.keys(deduplicatedData[0]).join(',')
    const rows = deduplicatedData.map(row => 
      Object.values(row).map(value => 
        typeof value === 'string' ? `"${value}"` : value
      ).join(',')
    )
    const csvContent = [headers, ...rows].join('\n')
    return new Blob([csvContent], { type: 'text/csv' })
  }

  // Handle Excel files
  const worksheet = XLSX.utils.json_to_sheet(deduplicatedData)
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Deduplicated')

  const excelBuffer = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' })
  return new Blob([excelBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
}

