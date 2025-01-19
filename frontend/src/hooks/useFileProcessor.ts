import { useState } from 'react'
import { processExcelFile, createDeduplicatedFile } from '@/utils/fileUtils'
import { GroupType } from '@/types'

export function useFileProcessor() {
  const [duplicates, setDuplicates] = useState<GroupType[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [originalFile, setOriginalFile] = useState<File | null>(null)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000'

  const processFile = async (file: File, trainingData: any) => {
    try {
      setIsLoading(true)
      setError(null)
      setDuplicates([])
      setProgress(0)
      setOriginalFile(file)

      const formData = new FormData()
      formData.append('files', file)
      const queryParams = new URLSearchParams({
        similarity_threshold: '0.5',
        training_data: JSON.stringify(trainingData)
      })
      const response = await fetch(
        `${BASE_URL}/dedupe/?${queryParams}`,
        {
          method: 'POST',
          body: formData,
        }
      )

      if (!response.ok) {
        throw new Error('Failed to process file')
      }

      const result = await response.json()
      if (result.status === 'needs_training') {
        return result.pairs
      } else {
        setDuplicates(result.duplicates)
      }

      // Simulate progress
      for (let i = 0; i <= 100; i += 10) {
        setProgress(i)
        await new Promise((resolve) => setTimeout(resolve, 100))
      }
    } catch (error) {
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

  const downloadFile = async (rowsToRemove: number[]) => {
    if (originalFile) {
      const deduplicatedFile = await createDeduplicatedFile(originalFile, rowsToRemove)
      const url = URL.createObjectURL(deduplicatedFile)
      const a = document.createElement('a')
      a.href = url
      a.download = `deduplicated_${originalFile.name}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    }
  }

  return { processFile, resetAll, duplicates, isLoading, downloadFile, progress, error }
}

