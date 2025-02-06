import { useState } from 'react'
import { processExcelFile, createDeduplicatedFile } from '@/utils/fileUtils'
import { GroupType } from '@/types'
import toast from 'react-hot-toast'
import axios from 'axios'

export function useFileProcessor() {
  const [duplicates, setDuplicates] = useState<GroupType[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [originalFile, setOriginalFile] = useState<File | null>(null)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

  const processFile = async (file: File, trainingData: any, setTrainingData: any, selectedColumns?: string[]) => {
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
      selectedColumns != undefined ? formData.append('selected_columns', JSON.stringify(selectedColumns)) : null
      console.log("trainingData: ", trainingData)
      console.log("selectedColumns: ", selectedColumns)

      const response = await axios.post(`${BASE_URL}/dedupe`, formData, {
        timeout: 60 * 60 * 2000, // 2 hour timeout
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        maxContentLength: Infinity,
        maxBodyLength: Infinity,
        responseType: 'json',
        maxRedirects: 0
      });
      
      console.log("response: ", response)

      if (response.status !== 200) {
        throw new Error('Failed to process file')
      }

      const result = response.data
      if (result.status === 'needs_training') {
        return result.pairs
      } else {
        if (result.duplicates && result.duplicates.length > 0) {
          setDuplicates(result.duplicates)
          setTrainingData(null)
        }
        else{
          toast.error("No duplicates found. Need more training data.")
        }
      }

      // Simulate progress
      for (let i = 0; i <= 100; i += 10) {
        setProgress(i)
        await new Promise((resolve) => setTimeout(resolve, 100))
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'An error occurred')
      setError(error instanceof Error ? error.message : 'An error occurred')
    } finally {
      setIsLoading(false)
    }
  }

  const resetAll = () => {
    setDuplicates([])
    setOriginalFile(null)
    setProgress(0)
    setError(null)
  }

  const downloadFile = (recordsToRemove: number[]) => {
    try {
      // Create a map of record_id to cluster_id
      const clusterMap = new Map();
      duplicates.forEach(group => {
        group.records.forEach(record => {
          clusterMap.set(record.record_id, group.cluster_id);
        });
      });

      // Get all records and add cluster_id
      const allRecords = duplicates.flatMap(group => 
        group.records.map(record => ({
          ...record,
          cluster_id: clusterMap.get(record.record_id) + 1 || '-'
        }))
      );

      // Filter out records that should be removed
      const filteredRecords = allRecords.filter(
        record => !recordsToRemove.includes(+record.record_id)
      );

      // Convert records to CSV
      const headers = Object.keys(filteredRecords[0]);
      const csvContent = [
        headers.join(','),
        ...filteredRecords.map(record => 
          headers.map(header => {
            const value = record[header];
            // Handle values that might contain commas
            return typeof value === 'string' && value.includes(',') 
              ? `"${value}"`
              : value;
          }).join(',')
        )
      ].join('\n');

      // Create and download the file
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);
      link.setAttribute('href', url);
      link.setAttribute('download', 'deduplicated_data.csv');
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (error) {
      console.error('Error downloading file:', error);
      toast.error('Error downloading file');
    }
  };

  return { processFile, resetAll, duplicates, isLoading, downloadFile, progress, error }
}

