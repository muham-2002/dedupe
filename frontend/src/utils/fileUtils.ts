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


// Helper function to read a file as text
export const readFileAsText = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsText(file);
  });
};

// Main function to handle file processing
export const mergeCSVFiles = async (files: File[], mapping: Record<string, string>) => {
  if (files.length !== 2) {
    throw new Error('Please select exactly 2 CSV files');
  }

  // Read both files
  const [file1Content, file2Content] = await Promise.all([
    readFileAsText(files[0]),
    readFileAsText(files[1])
  ]);

  // Split into lines and parse headers
  const file1Lines = file1Content.split('\n');
  const file2Lines = file2Content.split('\n');
  const file1Headers = file1Lines[0].split(',').map(h => h.trim());
  const file2Headers = file2Lines[0].split(',').map(h => h.trim());

  // Create mapping from file2 column index to file1 column index
  const columnMapping: Record<number, number> = {};
  Object.entries(mapping).forEach(([sourceCol, targetCol]) => {
    const file2Index = file2Headers.indexOf(sourceCol);
    const file1Index = file1Headers.indexOf(targetCol);
    if (file2Index !== -1 && file1Index !== -1) {
      columnMapping[file2Index] = file1Index;
    }
  });

  // Process file1 data rows
  const mergedData = [file1Lines[0]]; // Start with file1 headers
  const file1Data = file1Lines.slice(1).map(line => line.split(',').map(cell => cell.trim()));
  mergedData.push(...file1Data.map(row => row.join(',')));

  // Process and map file2 data rows
  const file2Data = file2Lines.slice(1).map(line => line.split(',').map(cell => cell.trim()));
  file2Data.forEach(row2 => {
    console.log(row2);
    const newRow = Array(file1Headers.length).fill('');
    Object.entries(columnMapping).forEach(([file2Index, file1Index]) => {
      newRow[file1Index] = row2[Number(file2Index)];
    });
    mergedData.push(newRow.join(','));
  });

  // Create new Blob with merged content
  const mergedBlob = new Blob([mergedData.join('\n')], { type: 'text/csv' });
  console.log(mergedBlob)
  return mergedBlob;
};

// Helper function to read file as ArrayBuffer
const readFileAsBuffer = (file: File): Promise<ArrayBuffer> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as ArrayBuffer);
    reader.onerror = reject;
    reader.readAsArrayBuffer(file);
  });
};

// Main merge function
export const mergeXLSXFiles = async (files: File[], mapping: Record<string, string>): Promise<Blob> => {
  if (files.length !== 2) {
    throw new Error('Please select exactly 2 XLSX files');
  }

  // Read and parse all files
  const workbooks = await Promise.all(
    files.map(async (file) => {
      const buffer = await readFileAsBuffer(file);
      return XLSX.read(buffer, { type: 'array' });
    })
  );

  // Get data from both workbooks
  const wb1 = workbooks[0];
  const wb2 = workbooks[1];
  const sheet1 = wb1.Sheets[wb1.SheetNames[0]];
  const sheet2 = wb2.Sheets[wb2.SheetNames[0]];

  // Convert to JSON with headers
  const file1Data = XLSX.utils.sheet_to_json(sheet1, { header: 1 });
  const file2Data = XLSX.utils.sheet_to_json(sheet2, { header: 1 });

  // Get headers
  const file1Headers = file1Data[0] as string[];
  const file2Headers = file2Data[0] as string[];

  // Create mapping from file2 column index to file1 column index
  const columnMapping: Record<number, number> = {};
  Object.entries(mapping).forEach(([sourceCol, targetCol]) => {
    const file2Index = file2Headers.indexOf(sourceCol);
    const file1Index = file1Headers.indexOf(targetCol);
    if (file2Index !== -1 && file1Index !== -1) {
      columnMapping[file2Index] = file1Index;
    }
  });
  // Start with file1 data
  const mergedData: any[][] = [...file1Data as any[][]];

  // Process and map file2 data rows
  const file2Rows = file2Data.slice(1) as any[][];
  file2Rows.forEach(row2 => {
    const newRow = Array(file1Headers.length).fill('');
    Object.entries(columnMapping).forEach(([file2Index, file1Index]) => {
      newRow[file1Index] = row2[Number(file2Index)];
    });
    mergedData.push(newRow);
  });

  // Create new workbook with merged data
  const newWorkbook = XLSX.utils.book_new();
  const newWorksheet = XLSX.utils.aoa_to_sheet(mergedData);
  
  XLSX.utils.book_append_sheet(
    newWorkbook,
    newWorksheet,
    'Merged Data'
  );

  // Generate merged file
  const mergedBuffer = XLSX.write(newWorkbook, {
    type: 'array',
    bookType: 'xlsx',
  });

  // Create and return Blob
  return new Blob([mergedBuffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });
};