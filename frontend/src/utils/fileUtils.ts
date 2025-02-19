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

// Helper function to check if a row is empty
const isEmptyRow = (row: any[]): boolean => {
  return row.every(cell => cell === '' || cell === null || cell === undefined);
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

  // Get mapped headers
  const mappedTargetHeaders = new Set(Object.keys(mapping)); // Headers from file1 that are mapped
  const mappedSourceHeaders = new Set(Object.values(mapping)); // Headers from file2 that are mapped to
  
  // Get unmapped headers from both files
  const unmappedFile1Headers = file1Headers.filter(h => !mappedTargetHeaders.has(h));
  const unmappedFile2Headers = file2Headers.filter(h => !mappedSourceHeaders.has(h));
  
  // Create final headers array:
  // 1. Mapped columns from file1 (target columns)
  // 2. Unmapped columns from file1
  // 3. Unmapped columns from file2
  const finalHeaders = [
    ...Array.from(mappedTargetHeaders),
    ...unmappedFile1Headers,
    ...unmappedFile2Headers
  ];

  // Create mapping from file2 column index to final header index
  const columnMapping: Record<number, number> = {};
  Object.entries(mapping).forEach(([targetCol, sourceCol]) => {
    const file2Index = file2Headers.indexOf(sourceCol);
    const finalIndex = finalHeaders.indexOf(targetCol);
    if (file2Index !== -1 && finalIndex !== -1) {
      columnMapping[file2Index] = finalIndex;
    }
  });

  // Process file1 data rows
  const mergedData = [finalHeaders.join(',')]; // Start with final headers
  const file1Data = file1Lines.slice(1)
    .map(line => line.split(',').map(cell => cell.trim()))
    .filter(row => !isEmptyRow(row)); // Filter out empty rows
  
  // Add file1 rows
  file1Data.forEach((row1, idx) => {
    const newRow = Array(finalHeaders.length).fill('');
    
    // Fill all columns from file1
    file1Headers.forEach((header, index) => {
      const finalIndex = finalHeaders.indexOf(header);
      if (finalIndex !== -1) {
        newRow[finalIndex] = row1[index];
      }
    });
    
    // Add source file name
    newRow.push(files[0].name);
    
    mergedData.push(newRow.join(','));
  });

  // Process file2 data rows
  const file2Data = file2Lines.slice(1)
    .map(line => line.split(',').map(cell => cell.trim()))
    .filter(row => !isEmptyRow(row)); // Filter out empty rows
  
  // Add file2 rows
  file2Data.forEach((row2, idx) => {
    const newRow = Array(finalHeaders.length).fill('');
    
    // Fill mapped columns using mapping
    Object.entries(columnMapping).forEach(([file2Index, finalIndex]) => {
      newRow[finalIndex] = row2[Number(file2Index)];
    });
    
    // Fill only unmapped columns from file2
    file2Headers.forEach((header, index) => {
      if (!mappedSourceHeaders.has(header)) {
        const finalIndex = finalHeaders.indexOf(header);
        if (finalIndex !== -1) {
          newRow[finalIndex] = row2[index];
        }
      }
    });
    
    // Add source file name
    newRow.push(files[1].name);
    
    mergedData.push(newRow.join(','));
  });

  // Add source_file to headers if not already present
  if (!finalHeaders.includes('source_file')) {
    finalHeaders.push('source_file');
    mergedData[0] = finalHeaders.join(',');
  }


  // Create new Blob with merged content
  return new Blob([mergedData.join('\n')], { type: 'text/csv' });
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

  // Get mapped headers
  const mappedTargetHeaders = new Set(Object.keys(mapping)); // Headers from file1 that are mapped
  const mappedSourceHeaders = new Set(Object.values(mapping)); // Headers from file2 that are mapped to
  
  // Get unmapped headers from both files
  const unmappedFile1Headers = file1Headers.filter(h => !mappedTargetHeaders.has(h));
  const unmappedFile2Headers = file2Headers.filter(h => !mappedSourceHeaders.has(h));
  
  // Create final headers array:
  // 1. Mapped columns from file1 (target columns)
  // 2. Unmapped columns from file1
  // 3. Unmapped columns from file2
  const finalHeaders = [
    ...Array.from(mappedTargetHeaders),
    ...unmappedFile1Headers,
    ...unmappedFile2Headers,
    'source_file' // Add source_file column
  ];

  // Create mapping from file2 column index to final header index
  const columnMapping: Record<number, number> = {};
  Object.entries(mapping).forEach(([targetCol, sourceCol]) => {
    const file2Index = file2Headers.indexOf(sourceCol);
    const finalIndex = finalHeaders.indexOf(targetCol);
    if (file2Index !== -1 && finalIndex !== -1) {
      columnMapping[file2Index] = finalIndex;
    }
  });

  // Initialize merged data with headers
  const mergedData: any[][] = [finalHeaders];

  // Process file1 rows
  const file1Rows = file1Data.slice(1) as any[][];
  file1Rows
    .filter(row => !isEmptyRow(row)) // Filter out empty rows
    .forEach((row1, idx) => {
      const newRow = Array(finalHeaders.length).fill('');
      
      // Fill mapped columns from file1
      file1Headers.forEach((header, index) => {
        const finalIndex = finalHeaders.indexOf(header);
        if (finalIndex !== -1) {
          newRow[finalIndex] = row1[index];
        }
      });
      
      // Add source file name
      newRow[finalHeaders.indexOf('source_file')] = files[0].name;
      
      mergedData.push(newRow);
    });

  // Process file2 rows
  const file2Rows = file2Data.slice(1) as any[][];
  file2Rows
    .filter(row => !isEmptyRow(row)) // Filter out empty rows
    .forEach((row2, idx) => {
      const newRow = Array(finalHeaders.length).fill('');
      
      // Fill mapped columns using mapping
      Object.entries(columnMapping).forEach(([file2Index, finalIndex]) => {
        newRow[finalIndex] = row2[Number(file2Index)];
      });
      
      // Fill only unmapped columns from file2
      file2Headers.forEach((header, index) => {
        if (!mappedSourceHeaders.has(header)) {
          const finalIndex = finalHeaders.indexOf(header);
          if (finalIndex !== -1) {
            newRow[finalIndex] = row2[index];
          }
        }
      });
      
      // Add source file name
      newRow[finalHeaders.indexOf('source_file')] = files[1].name;
      
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