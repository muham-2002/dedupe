/* eslint-disable */
'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '@/components/ui/card'
import { useFileProcessor } from '@/hooks/useFileProcessor'
import FileUpload from '@/components/FileUpload'
import DuplicateGroup from '@/components/DuplicateGroups'
import { AlertCircle, CheckCircle2 } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import dynamic from 'next/dynamic'
import FilePreview from '@/components/FilePreview'
import toast from 'react-hot-toast';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"


const Confetti = dynamic(() => import('@/components/Confetti'), { ssr: false })

export default function Home() {
  const [file, setFile] = useState<File | null>(null)
  const { processFile, duplicates, downloadFile, isLoading, progress, error, resetAll } = useFileProcessor()
  const [showConfetti, setShowConfetti] = useState(false)
  const [selectedRecords, setSelectedRecords] = useState<Record<number, any[]>>({})
  const [apiCalled, setApiCalled] = useState(false)
  const [trainingData, setTrainingData] = useState<any>(null)
  const [currentPairIndex, setCurrentPairIndex] = useState<number>(0)
  const [userResponses, setUserResponses] = useState<Record<number, 'y' | 'n' | 'u'>>({})
  const [isFinishLoading, setIsFinishLoading] = useState(false)
  const [selectedColumns, setSelectedColumns] = useState<string[]>([])
  const [availableColumns, setAvailableColumns] = useState<string[]>([])

  const handleClearAll = () => {
    setSelectedRecords({})
    setShowConfetti(false)
    setApiCalled(false)
    setFile(null)
    setTrainingData(null)
    setCurrentPairIndex(0)
    setUserResponses({})
    setIsFinishLoading(false)
    resetAll()
  }

  const handleFileUpload = async (uploadedFile: File) => {
    setFile(uploadedFile)
    setSelectedRecords({})
    setShowConfetti(false)
    setSelectedColumns([])
  }

  const handleRemoveDuplicates = async () => {
    if (file && selectedColumns.length >= 2) {
      setTrainingData(null)
      setCurrentPairIndex(0)
      setUserResponses({})
      setSelectedRecords({})
      resetAll()
      setApiCalled(true)
      setSelectedRecords({})
      setShowConfetti(false)
      const pairs = await processFile(file, null, setTrainingData, selectedColumns)
      console.log(pairs)
      setTrainingData(pairs)
    } else {
      toast.error("Please select at least two columns for matching")
    }
  }

  const handleSelectRow = (clusterId: number, rowIndex: number, record: any, isSelected: boolean) => {
    console.log(duplicates)
    setSelectedRecords(prev => {
      const newState = { ...prev }
      if (!newState[clusterId]) {
        newState[clusterId] = []
      }

      if (isSelected) {
        newState[clusterId] = [...newState[clusterId], record]
      } else {
        newState[clusterId] = newState[clusterId].filter(r => r.record_id !== record.record_id)
      }

      if (newState[clusterId].length === 0) {
        delete newState[clusterId]
      }

      return newState
    })
  }

  const handleRemoveAllDuplicates = () => {
    const newSelectedRecords: Record<number, any[]> = {}

    duplicates.forEach(group => {
      // Skip the first record (index 0) and select all others
      const duplicatesToRemove = group.records.slice(1)
      if (duplicatesToRemove.length > 0) {
        newSelectedRecords[group.cluster_id] = duplicatesToRemove
      }
    })

    setSelectedRecords(newSelectedRecords)
  }

  const getSelectedRowsForGroup = (clusterId: number) => {
    const selectedRecordsForGroup = selectedRecords[clusterId] || []
    return duplicates
      .find(g => g.cluster_id === clusterId)?.records
      .map((record: any, index: number) =>
        selectedRecordsForGroup.some(r => r.record_id === record.record_id) ? index : -1
      )
      .filter((index: number) => index !== -1) || []
  }

  const downloadWithDuplicates = () => {
    // Download all records, including duplicates
    downloadFile([])
  }

  // Calculate max width for each column across all groups
  const getColumnWidths = () => {
    if (!duplicates.length) return {}

    return duplicates.reduce((acc, group) => {
      Object.keys(group.records[0]).forEach(key => {
        const maxInGroup = Math.max(
          key.length,
          ...group.records.map(record => String(record[key]).length)
        )
        acc[key] = Math.max(acc[key] || 0, maxInGroup)
      })
      return acc
    }, {} as Record<string, number>)
  }

  const columnWidths = getColumnWidths()

  const handleTrainingResponse = (response: 'y' | 'n' | 'u') => {
    setUserResponses(prev => ({
      ...prev,
      [currentPairIndex]: response
    }))
    setCurrentPairIndex(prev => prev + 1)
  }

  const handleFinishTraining = async () => {
    if (file) {
      setIsFinishLoading(true)
      // Filter out uncertain responses and format training data
      const trainingPairs = Object.entries(userResponses)
        .filter(([_, response]) => response !== 'u')
        .map(([index, response]) => ({
          ...trainingData[parseInt(index)],
          answer: response
        }))

      setApiCalled(true)
      setSelectedRecords({})
      setShowConfetti(false)
      await processFile(file, trainingPairs, setTrainingData)
      setIsFinishLoading(false)
    }
  }

  const handleDownloadDeduplicated = () => {
    const recordsToRemove = Object.values(selectedRecords)
      .flat()
      .map(record => +record.record_id);
    console.log(recordsToRemove)
    // Show warning if no duplicates are selected for removal
    if (recordsToRemove.length === 0) {
      toast.error("No duplicates selected for removal. The downloaded file will be identical to the original.");
      return;
    }

    // Download file excluding the selected records
    downloadFile(recordsToRemove);
  }

  const renderTrainingInterface = () => {
    if (!trainingData) return null

    // If we've reached the end of training pairs and have some responses
    if (currentPairIndex >= trainingData.length && Object.keys(userResponses).length > 0) {
      handleFinishTraining()
      return (
        <Card className="mb-8">
          <CardContent className="flex items-center justify-center p-8">
            <div className="text-center">
              <div className="mb-4">Processing your responses...</div>
              <div className="relative h-2 overflow-hidden rounded-full bg-secondary w-64">
                <div className="absolute inset-0 w-1/3 bg-primary animate-loading-bar"></div>
              </div>
            </div>
          </CardContent>
        </Card>
      )
    }

    if (currentPairIndex >= trainingData.length) return null

    // Add check for minimum training data size
    if (trainingData.length < 10) {
      return (
        <Alert className="mb-4">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>File Too Small</AlertTitle>
          <AlertDescription>
            Your file is too small for training. It needs at least 10 record pairs to proceed with training.
          </AlertDescription>
        </Alert>
      )
    }

    const currentPair = trainingData[currentPairIndex]

    // Count yes and no responses separately
    const yesResponses = Object.values(userResponses).filter(r => r === 'y').length
    const noResponses = Object.values(userResponses).filter(r => r === 'n').length
    const totalResponses = Object.values(userResponses).filter(r => r !== 'u').length
    const hasEnoughResponses = yesResponses >= 2 && noResponses >= 2 && totalResponses >= 15
    
    return (
      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Are these records duplicates?</CardTitle>
          <div className="text-sm text-muted-foreground mt-2">
            <p>
              Progress: {totalResponses}/15 responses (Yes: {yesResponses}/2, No: {noResponses}/2)
            </p>
            {!hasEnoughResponses && (
              <p className="text-destructive mt-1">
                Need at least 2 of each response type and 15 total responses
              </p>
            )}
          </div>
        </CardHeader>
        <CardFooter className="flex justify-center gap-4">
          {isFinishLoading ? (
            <div className="flex items-center gap-2">
              <Button disabled>
                Processing...
              </Button>
            </div>
          ) : (
            <>
              <Button
                onClick={() => handleTrainingResponse('y')}
                variant="default"
              >
                Yes
              </Button>
              <Button
                onClick={() => handleTrainingResponse('n')}
                variant="default"
              >
                No
              </Button>
              <Button
                onClick={() => handleTrainingResponse('u')}
                variant="default"
              >
                Uncertain
              </Button>
              {hasEnoughResponses && (
                <Button
                  onClick={handleFinishTraining}
                  variant="default"
                >
                  Finish
                </Button>
              )}
            </>
          )}
        </CardFooter>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div className="border p-4 rounded-md">
              <h3 className="font-bold mb-2">Record 1</h3>
              {Object.entries(currentPair[0]).map(([key, value]) => (
                <div key={key} className="mb-1">
                  <span className="font-semibold">{key}:</span> {value as string}
                </div>
              ))}
            </div>
            <div className="border p-4 rounded-md">
              <h3 className="font-bold mb-2">Record 2</h3>
              {Object.entries(currentPair[1]).map(([key, value]) => (
                <div key={key} className="mb-1">
                  <span className="font-semibold">{key}:</span> {value as string}
                </div>
              ))}
            </div>
          </div>
        </CardContent>

      </Card>
    )
  }

  const renderColumnSelection = () => {
    if (!file) return null;

    const handleAddColumn = (value: string) => {
      if (value && !selectedColumns.includes(value)) {
        setSelectedColumns([...selectedColumns, value]);
      }
    };

    const handleRemoveColumn = (columnToRemove: string) => {
      setSelectedColumns(selectedColumns.filter(col => col !== columnToRemove));
    };

    return (
      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Select Matching Columns</CardTitle>
          <p className="text-sm text-muted-foreground mt-2">
            Select columns that are important for matching. Choose columns that:
          </p>
          <ul className="text-sm text-muted-foreground list-disc list-inside mt-1">
            <li>Don't contain null or empty values</li>
            <li>Have consistent formatting</li>
            <li>Are likely to be similar for duplicate records</li>
          </ul>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {selectedColumns.map((column, index) => (
              <div 
                key={column} 
                className="flex items-center gap-2 bg-secondary rounded-md px-3 py-1"
              >
                <span className="text-sm">{column}</span>
                <button
                  onClick={() => handleRemoveColumn(column)}
                  className="text-muted-foreground hover:text-destructive"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <Select onValueChange={handleAddColumn}>
              <SelectTrigger className="w-[200px]">
                <SelectValue placeholder="Add column" />
              </SelectTrigger>
              <SelectContent>
                {availableColumns
                  .filter(col => !selectedColumns.includes(col))
                  .map(col => (
                    <SelectItem key={col} value={col}>
                      {col}
                    </SelectItem>
                  ))
                }
              </SelectContent>
            </Select>
          </div>
          {selectedColumns.length < 2 && (
            <p className="text-sm text-destructive">
              Please select at least 2 columns for matching
            </p>
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-background via-muted to-background">
      <div className="container mx-auto py-8 px-4">
        <div className="mb-8 text-center space-y-2">
          <h1 className="text-4xl font-bold tracking-tight text-primary">File Deduplication Tool</h1>
          <p className="text-muted-foreground">Upload your file and let us handle the duplicates for you</p>
        </div>

        {!trainingData && !duplicates.length && (<div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <div className="space-y-4">
            <Card className="border-none shadow-md h-full">
              <CardHeader className="pb-4">
                <CardTitle className="text-xl font-semibold">Upload File</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <FileUpload onFileUpload={handleFileUpload} handleClearAll={handleClearAll} file={file} isLoading={isLoading} />
                {file && renderColumnSelection()}
                {file && selectedColumns.length >= 2 && (
                  <div className="flex gap-2">
                    <Button
                      onClick={handleRemoveDuplicates}
                      disabled={isLoading}
                      className="w-full"
                    >
                      {isLoading ? 'Processing...' : 'Find Duplicates'}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={handleClearAll}
                      disabled={isLoading}
                      className="w-full"
                    >
                      Clear
                    </Button>
                  </div>
                )}
                {isLoading && (
                  <div className="space-y-4">
                    <div className="relative h-2 overflow-hidden rounded-full bg-secondary">
                      <div className="absolute inset-0 w-1/3 bg-primary animate-loading-bar"></div>
                    </div>
                    <p className="text-sm text-muted-foreground text-center">Processing your file...</p>
                  </div>
                )}
                {error && (
                  <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertTitle>Error</AlertTitle>
                    <AlertDescription>{error}</AlertDescription>
                  </Alert>
                )}
              </CardContent>
            </Card>
          </div>

          <FilePreview file={file} setAvailableColumns={setAvailableColumns}/>
        </div>
        )}

        {/* Training interface */}
        {trainingData && !duplicates.length && (
          <div className="flex justify-end mb-4">
            <Button
              variant="outline"
              onClick={handleClearAll}
              className="button-hover shadow-md"
            >
              Reset
            </Button>
          </div>
        )}
        {trainingData && !duplicates.length && renderTrainingInterface()}

        {error && (
          <Alert variant="destructive" className="mb-4 glass-effect">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {duplicates.length === 0 && !isLoading && file && apiCalled && !trainingData && (
          <div className="text-center p-8 glass-effect rounded-lg">
            <div className="inline-block rounded-full bg-secondary p-3 animate-float">
              <AlertCircle className="h-6 w-6 text-secondary-foreground" />
            </div>
            <p className="mt-2 text-muted-foreground">No duplicates found in your file.</p>
          </div>
        )}

        {duplicates.length > 0 && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <h2 className="text-2xl font-semibold bg-gradient-to-r from-primary to-primary/80 bg-clip-text">
                  Duplicate Groups Found
                </h2>
                <Button
                  variant="outline"
                  onClick={handleClearAll}
                  className="button-hover shadow-md"
                >
                  Reset
                </Button>
              </div>
              <div className="flex gap-2">
                <Button
                  onClick={handleRemoveAllDuplicates}
                  variant="secondary"
                  className="button-hover shadow-md"
                >
                  Remove All Duplicates
                </Button>
                <Button
                  onClick={downloadWithDuplicates}
                  variant="outline"
                  className="button-hover shadow-md"
                >
                  Download with Duplicates
                </Button>
                <Button
                  onClick={handleDownloadDeduplicated}
                  className="bg-gradient-to-r from-primary to-primary/80 hover:from-primary/90 hover:to-primary/70 button-hover shadow-md"
                >
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                  Download Deduplicated File
                </Button>
              </div>
            </div>
            <div className="space-y-4">
              {duplicates
                .sort((a, b) => a.cluster_id - b.cluster_id)
                .map((group) => (
                  <DuplicateGroup
                    key={group.cluster_id}
                    group={group}
                    onSelectRow={handleSelectRow}
                    columnWidths={columnWidths}
                    selectedRows={getSelectedRowsForGroup(group.cluster_id)}
                  />
                ))}
            </div>
          </div>
        )}
      </div>
      {showConfetti && <Confetti />}
    </main>
  )
}
