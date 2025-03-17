import { useState } from 'react'
import { GroupType } from '@/types'
import toast from 'react-hot-toast'
import axios from 'axios'
import Papa from 'papaparse'
import * as XLSX from 'xlsx'

export function useFileProcessor() {
  const [duplicates, setDuplicates] = useState<GroupType[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [originalFile, setOriginalFile] = useState<File | null>(null)
  const [originalFileData, setOriginalFileData] = useState<any>([])
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [isFileNameDialogOpen, setIsFileNameDialogOpen] = useState(false)
  const [pendingDownload, setPendingDownload] = useState<{
    content: string;
    type: 'original' | 'clean';
  } | null>(null)
  const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

  const processFile = async (
    file: File,
    trainingData: any,
    selectedColumns?: string[],
    isReprocessing: boolean = false
  ) => {
    try {
      setIsLoading(true)
      setError(null)
      setDuplicates([])
      setProgress(0)
      setOriginalFile(file)

      const formData = new FormData()
      formData.append('files', file)
      formData.append('similarity_threshold', '0.2')
      formData.append('training_data', JSON.stringify(trainingData))
      if (isReprocessing) {
        formData.append('is_reprocessing', 'true')
      }
      selectedColumns != undefined ? formData.append('selected_columns', JSON.stringify(selectedColumns)) : null

      if (originalFile) {
        await readAndStoreOriginalFile(originalFile)
      }

      const response = await axios.post(`${BASE_URL}/dedupe`, formData, {
        timeout: 60 * 60 * 2000,
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        maxContentLength: Infinity,
        maxBodyLength: Infinity,
        responseType: 'json',
        maxRedirects: 0
      });


      if (response.status !== 200) {
        throw new Error('Failed to process file')
      }

      const result = response.data
      // Simulate progress
      for (let i = 0; i <= 100; i += 10) {
        setProgress(i)
        await new Promise((resolve) => setTimeout(resolve, 100))
      }
      if (result.status === 'needs_training') {
        return [result, 'training'];
      } else {
        if (result.duplicates && result.duplicates.length > 0) {
          setDuplicates(result.duplicates)
          return [result, 'reviewing'];
        }
        else {
          toast.error("No duplicates found. Need more training data.")
          return [result, 'training'];
        }
      }


    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'An error occurred')
      setError(error instanceof Error ? error.message : 'An error occurred')
    } finally {
      setIsLoading(false)
    }
  }

  const readAndStoreOriginalFile = async (file: File) => {
    return new Promise((resolve, reject) => {
      if (file.name.endsWith('.csv')) {
        Papa.parse(file, {
          header: true,
          complete: (results) => {
            // Add row numbers as record_id and source file name (accounting for header and 1-based indexing)
            const dataWithIds = results.data.map((row: any) => {
              const recordId = results.data.indexOf(row).toString();
              return {
                ...row,
                record_id: recordId,
                __source_file: file.name // Add source file name but don't expose it
              };
            }) as any[];
            setOriginalFileData(dataWithIds);
            resolve(dataWithIds);
          },
          error: reject
        });
      } else if (file.name.endsWith('.xlsx') || file.name.endsWith('.xls')) {
        const reader = new FileReader();
        reader.onload = (e) => {
          try {
            const data = new Uint8Array(e.target?.result as ArrayBuffer);
            const workbook = XLSX.read(data, { type: 'array' });
            const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
            const jsonData = XLSX.utils.sheet_to_json(firstSheet);
            // Add row numbers as record_id and source file name
            const dataWithIds = jsonData.map((row: any) => {
              const recordId = jsonData.indexOf(row).toString();
              return {
                ...row,
                record_id: recordId,
                __source_file: file.name // Add source file name but don't expose it
              };
            }) as any[];
            setOriginalFileData(dataWithIds);
            resolve(dataWithIds);
          } catch (error) {
            reject(error);
          }
        };
        reader.onerror = reject;
        reader.readAsArrayBuffer(file);
      }
    });
  };

  const resetAll = () => {
    setDuplicates([])
    setOriginalFile(null)
    setOriginalFileData([])
    setProgress(0)
    setError(null)
  }

  const handleDownload = (content: string, fileName: string) => {
    const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', fileName);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    setIsFileNameDialogOpen(false);
    setPendingDownload(null);
  };

  const downloadFile = async (recordsToRemove: number[]) => {
    try {
      // Create a set of records to remove for faster lookup
      const recordsToRemoveSet = new Set(recordsToRemove);

      // Create a map of record_id to source file from originalFileData
      const recordIdToSourceFile = new Map(
        originalFileData.map((record: any) => [record.record_id, record.source_file ? record.source_file : record.__source_file])
      );

      // Collect all records from duplicate groups
      const processedRecords = duplicates.flatMap(group =>
        group.records
          // Filter out records that are marked for removal
          .filter(record => !recordsToRemoveSet.has(+record.record_id))
          .map(record => ({
            ...record,
            cluster_id: (group.cluster_id + 1).toString(),
            confidence_score: record.confidence_score || '',
            // Look up the source file from originalFileData using record_id
            source_file: recordIdToSourceFile.get(record.record_id) || ''
          }))
      );

      // Get all headers from the processed records except the special columns
      const specialColumns = ['cluster_id', 'confidence_score', 'source_file', '__source_file', 'record_id'];

      const regularHeaders = Array.from(
        new Set(
          processedRecords.flatMap(record => Object.keys(record))
        )
      ).filter(header => !specialColumns.includes(header)).sort();

      // Combine headers with cluster_id first, then regular headers, then remaining special columns
      const allHeaders = [
        'cluster_id',
        ...regularHeaders,
        'record_id',
        'confidence_score',
        'source_file'
      ];

      // Process and format values while creating the array
      const formatValue = (value: any) => {
        if (value === null || value === undefined || value === 'N/A') {
          return '';
        }
        const stringValue = String(value);
        if (stringValue.includes(',') || stringValue.includes('\n') || stringValue.includes('"')) {
          return `"${stringValue.replace(/"/g, '""')}"`;
        }
        return stringValue;
      };

      // Convert records to CSV with consistent columns
      const csvContent = [
        allHeaders.join(','),
        ...processedRecords.map(record => {
          // Create and format values in one pass
          return [
            formatValue(record['cluster_id']), // cluster_id first
            ...regularHeaders.map(header => formatValue(record[header])), // regular columns
            formatValue(record['record_id']), // special columns at the end
            formatValue(record['confidence_score']),
            formatValue(record['source_file'])
          ].join(',');
        })
      ].join('\n');

      setPendingDownload({
        content: csvContent,
        type: recordsToRemove.length > 0 ? 'clean' : 'original'
      });
      setIsFileNameDialogOpen(true);

    } catch (error) {
      console.error('Error downloading file:', error);
      toast.error('Error downloading file');
    }
  };

  return { 
    processFile, 
    resetAll, 
    duplicates, 
    isLoading, 
    downloadFile, 
    progress, 
    error,
    isFileNameDialogOpen,
    setIsFileNameDialogOpen,
    pendingDownload,
    handleDownload
  }
}

