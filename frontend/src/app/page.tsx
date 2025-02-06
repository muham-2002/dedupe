/* eslint-disable */
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardFooter,
} from "@/components/ui/card";
import { useFileProcessor } from "@/hooks/useFileProcessor";
import FileUpload from "@/components/FileUpload";
import DuplicateGroup from "@/components/DuplicateGroups";
import {
  AlertCircle,
  CheckCircle2,
  Download,
  Loader2,
  RotateCcw,
  X,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import dynamic from "next/dynamic";
import FilePreview from "@/components/FilePreview";
import toast from "react-hot-toast";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import ColumnMapper from "@/components/ColumnMapper";
import Papa from "papaparse";
import { mergeCSVFiles, mergeXLSXFiles } from "@/utils/fileUtils";

const Confetti = dynamic(() => import("@/components/Confetti"), { ssr: false });

// First, add this type above the Home component
type SortOption = "confidence-high" | "confidence-low" | "group-id";

// Add these types at the top
type FileState = File[];

interface ParseResult {
  data: Record<string, unknown>[];
  errors: Papa.ParseError[];
  meta: Papa.ParseMeta;
}

export default function Home() {
  const [files, setFiles] = useState<FileState>([]);
  const {
    processFile,
    duplicates,
    downloadFile,
    isLoading,
    progress,
    error,
    resetAll,
  } = useFileProcessor();
  const [showConfetti, setShowConfetti] = useState(false);
  const [selectedRecords, setSelectedRecords] = useState<Record<number, any[]>>(
    {}
  );
  const [apiCalled, setApiCalled] = useState(false);
  const [trainingData, setTrainingData] = useState<any>(null);
  const [currentPairIndex, setCurrentPairIndex] = useState<number>(0);
  const [userResponses, setUserResponses] = useState<
    Record<number, "y" | "n" | "u">
  >({});
  const [isFinishLoading, setIsFinishLoading] = useState(false);
  const [selectedColumns, setSelectedColumns] = useState<string[]>([]);
  const [availableColumns, setAvailableColumns] = useState<string[]>([]);
  const [sortOption, setSortOption] = useState<SortOption>("group-id");
  const [data, setData] = useState<any>(null);

  const handleClearAll = () => {
    setSelectedRecords({});
    setShowConfetti(false);
    setApiCalled(false);
    setFiles([]);
    setTrainingData(null);
    setCurrentPairIndex(0);
    setUserResponses({});
    setIsFinishLoading(false);
    resetAll();
  };

  const handleFileUpload = async (uploadedFiles: File[]) => {
    const newTotalFiles = files.length + uploadedFiles.length;
    if (newTotalFiles > 2) {
      toast.error("Maximum of 2 files allowed");
      return;
    }

    // Check if files have different extensions
    const extensions = uploadedFiles.map(file => file.name.split('.').pop()?.toLowerCase());
    const uniqueExtensions = new Set(extensions);
    
    if (uniqueExtensions.size > 1) {
      toast.error("All files must have the same extension");
      return;
    }

    setFiles((prev) => [...prev, ...uploadedFiles]);
    setSelectedRecords({});
    setShowConfetti(false);
    setSelectedColumns([]);
  };

  const handleRemoveFile = () => {
    // Clear all files
    setFiles([]);
    setSelectedColumns([]);
    setSelectedRecords({});
    setShowConfetti(false);
  };

  const handleRemoveDuplicates = async () => {
    if (files.length > 0 && selectedColumns.length >= 2) {
      setTrainingData(null);
      setCurrentPairIndex(0);
      setUserResponses({});
      setSelectedRecords({});
      resetAll();
      setApiCalled(true);
      setSelectedRecords({});
      setShowConfetti(false);
      const pairs = await processFile(
        files[0],
        null,
        setTrainingData,
        selectedColumns
      );
      console.log(pairs);
      setTrainingData(pairs);
    } else {
      toast.error("Please select at least two columns for matching");
    }
  };

  const handleSelectRow = (
    clusterId: number,
    rowIndex: number,
    record: any,
    isSelected: boolean
  ) => {
    console.log(duplicates);
    setSelectedRecords((prev) => {
      const newState = { ...prev };
      if (!newState[clusterId]) {
        newState[clusterId] = [];
      }

      if (isSelected) {
        newState[clusterId] = [...newState[clusterId], record];
      } else {
        newState[clusterId] = newState[clusterId].filter(
          (r) => r.record_id !== record.record_id
        );
      }

      if (newState[clusterId].length === 0) {
        delete newState[clusterId];
      }

      return newState;
    });
  };

  const handleRemoveAllDuplicates = () => {
    const newSelectedRecords: Record<number, any[]> = {};

    duplicates.forEach((group) => {
      // Skip the first record (index 0) and select all others
      const duplicatesToRemove = group.records.slice(1);
      if (duplicatesToRemove.length > 0) {
        newSelectedRecords[group.cluster_id] = duplicatesToRemove;
      }
    });

    setSelectedRecords(newSelectedRecords);
  };

  const getSelectedRowsForGroup = (clusterId: number) => {
    const selectedRecordsForGroup = selectedRecords[clusterId] || [];
    return (
      duplicates
        .find((g) => g.cluster_id === clusterId)
        ?.records.map((record: any, index: number) =>
          selectedRecordsForGroup.some((r) => r.record_id === record.record_id)
            ? index
            : -1
        )
        .filter((index: number) => index !== -1) || []
    );
  };

  const downloadWithDuplicates = () => {
    // Download all records, including duplicates
    downloadFile([]);
  };

  // Calculate max width for each column across all groups
  const getColumnWidths = () => {
    if (!duplicates.length) return {};

    return duplicates.reduce((acc, group) => {
      Object.keys(group.records[0]).forEach((key) => {
        const maxInGroup = Math.max(
          key.length,
          ...group.records.map((record) => String(record[key]).length)
        );
        acc[key] = Math.max(acc[key] || 0, maxInGroup);
      });
      return acc;
    }, {} as Record<string, number>);
  };

  const columnWidths = getColumnWidths();

  const handleTrainingResponse = (response: "y" | "n" | "u") => {
    setUserResponses((prev) => ({
      ...prev,
      [currentPairIndex]: response,
    }));
    setCurrentPairIndex((prev) => prev + 1);
  };

  const handleFinishTraining = async () => {
    if (files.length > 0) {
      setIsFinishLoading(true);
      // Filter out uncertain responses and format training data
      const trainingPairs = Object.entries(userResponses)
        .filter(([_, response]) => response !== "u")
        .map(([index, response]) => ({
          ...trainingData[parseInt(index)],
          answer: response,
        }));

      setApiCalled(true);
      setSelectedRecords({});
      setShowConfetti(false);
      await processFile(files[0], trainingPairs, setTrainingData);
      setIsFinishLoading(false);
    }
  };

  const handleDownloadDeduplicated = () => {
    const recordsToRemove = Object.values(selectedRecords)
      .flat()
      .map((record) => +record.record_id);
    console.log(recordsToRemove);
    // Show warning if no duplicates are selected for removal
    if (recordsToRemove.length === 0) {
      toast.error(
        "No duplicates selected for removal. The downloaded file will be identical to the original."
      );
      return;
    }

    // Download file excluding the selected records
    downloadFile(recordsToRemove);
  };

  const handleMappingComplete = async (
    mapping: Record<string, string>, 
    sourceFile: number, 
    targetFile: number
  ) => {
    if (!sourceFile || !targetFile) return;
    
    if (files[0].name.endsWith('.csv') && files[1].name.endsWith('.csv')) {
      const mergedBlob = await mergeCSVFiles([files[sourceFile-1], files[targetFile-1]], mapping);
      const mergedFile = new File([mergedBlob], `merged_${files[sourceFile-1].name.split('.')[0]}_${files[targetFile-1].name.split('.')[0]}.csv`, { type: "text/csv" });
      setFiles([mergedFile]);
    } else if (files[0].name.endsWith('.xlsx') && files[1].name.endsWith('.xlsx')) {
      const mergedBlob = await mergeXLSXFiles([files[sourceFile-1], files[targetFile-1]], mapping);
      const mergedFile = new File([mergedBlob], `merged_${files[sourceFile-1].name.split('.')[0]}_${files[targetFile-1].name.split('.')[0]}.xlsx`, { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
      setFiles([mergedFile]);
    }
  };

  const renderTrainingInterface = () => {
    if (!trainingData) return null;

    // If we've reached the end of training pairs and have some responses
    if (
      currentPairIndex >= trainingData.length &&
      Object.keys(userResponses).length > 0
    ) {
      handleFinishTraining();
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
      );
    }

    if (currentPairIndex >= trainingData.length) return null;

    // Add check for minimum training data size
    if (trainingData.length < 10) {
      return (
        <Alert className="mb-4">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>File Too Small</AlertTitle>
          <AlertDescription>
            Your file is too small for training. It needs at least 10 record
            pairs to proceed with training.
          </AlertDescription>
        </Alert>
      );
    }

    const currentPair = trainingData[currentPairIndex];

    // Count yes and no responses separately
    const yesResponses = Object.values(userResponses).filter(
      (r) => r === "y"
    ).length;
    const noResponses = Object.values(userResponses).filter(
      (r) => r === "n"
    ).length;
    const totalResponses = Object.values(userResponses).filter(
      (r) => r !== "u"
    ).length;
    const hasEnoughResponses =
      yesResponses >= 2 && noResponses >= 2 && totalResponses >= 15;

    return (
      <Card className="mb-8 border-2 border-muted">
        <CardHeader>
          <CardTitle>Are these records duplicates?</CardTitle>
          <div className="text-sm text-muted-foreground mt-2">
            <p>
              Progress: {totalResponses}/15 responses (Yes: {yesResponses}/5,
              No: {noResponses}/5)
            </p>
            {!hasEnoughResponses && (
              <p className="text-destructive mt-1">
                Need at least 5 of each response type and 15 total responses
              </p>
            )}
          </div>
        </CardHeader>
        <CardFooter className="flex justify-center gap-4">
          {isFinishLoading ? (
            <div className="flex items-center gap-2">
              <Button disabled className="flex items-center gap-2">
                <div className="animate-spin">
                  <Loader2 className="h-4 w-4" />
                </div>
                Processing...
              </Button>
            </div>
          ) : (
            <>
              <Button
                onClick={() => handleTrainingResponse("y")}
                className="bg-green-600 hover:bg-green-700 text-white font-medium flex items-center gap-2"
              >
                <span className="text-lg">✓</span>
                Yes, Duplicate
              </Button>
              <Button
                onClick={() => handleTrainingResponse("n")}
                className="bg-red-600 hover:bg-red-700 text-white font-medium flex items-center gap-2"
              >
                <span className="text-lg">✕</span>
                No, Different
              </Button>
              <Button
                onClick={() => handleTrainingResponse("u")}
                variant="secondary"
                className="bg-gray-200 hover:bg-gray-300 text-gray-700 font-medium flex items-center gap-2"
              >
                <span className="text-lg">?</span>
                Not Sure
              </Button>
              {hasEnoughResponses && (
                <Button
                  onClick={handleFinishTraining}
                  className="bg-blue-600 hover:bg-blue-700 text-white font-medium flex items-center gap-2"
                >
                  <span className="text-lg">→</span>
                  Complete Training
                </Button>
              )}
            </>
          )}
        </CardFooter>
        <CardContent>
          <div className="rounded-lg border overflow-hidden">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent bg-muted/50">
                    <TableHead className="text-xs font-bold whitespace-nowrap">
                      Field
                    </TableHead>
                    <TableHead className="text-xs font-bold whitespace-nowrap">
                      Record 1
                    </TableHead>
                    <TableHead className="text-xs font-bold whitespace-nowrap">
                      Record 2
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Object.keys(currentPair[0]).map((key) => (
                    <TableRow key={key} className="hover:bg-accent">
                      <TableCell className="text-xs py-2 font-medium text-muted-foreground">
                        {key}
                      </TableCell>
                      {[0, 1].map((index) => (
                        <TableCell
                          key={`${key}-${index}`}
                          className="text-xs py-2"
                        >
                          {currentPair[index][key] ? (
                            currentPair[index][key] === "nan" ? (
                              "N/A"
                            ) : (
                              (currentPair[index][key] as string)
                            )
                          ) : (
                            <em className="text-muted-foreground">Empty</em>
                          )}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  };

  const renderColumnSelection = () => {
    if (files.length === 0) return null;

    const handleAddColumn = (value: string) => {
      if (value && !selectedColumns.includes(value)) {
        setSelectedColumns([...selectedColumns, value]);
      }
    };

    const handleRemoveColumn = (columnToRemove: string) => {
      setSelectedColumns(
        selectedColumns.filter((col) => col !== columnToRemove)
      );
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
                  .filter((col) => !selectedColumns.includes(col))
                  .map((col) => (
                    <SelectItem key={col} value={col}>
                      {col}
                    </SelectItem>
                  ))}
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
  };

  // Add this sorting function inside the Home component
  const getSortedDuplicates = () => {
    if (!duplicates) return [];

    return [...duplicates].sort((a, b) => {
      switch (sortOption) {
        case "confidence-high":
          return (b.confidence_score ?? 0) - (a.confidence_score ?? 0);
        case "confidence-low":
          return (a.confidence_score ?? 0) - (b.confidence_score ?? 0);
        case "group-id":
          return a.cluster_id - b.cluster_id;
        default:
          return 0;
      }
    });
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-background via-muted/50 to-background">
      <div className="container mx-auto py-8 px-4">
        <div className="mb-8 text-center space-y-2">
          <h1 className="text-4xl font-bold tracking-tight text-primary">
            File Deduplication Tool
          </h1>
          <p className="text-muted-foreground">
            Upload your file and let us handle the duplicates for you
          </p>
        </div>

        {!trainingData && !duplicates.length && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <div className="space-y-4">
              <Card className="border-none shadow-md h-full">
                <CardHeader className="pb-4">
                  <CardTitle className="text-xl font-semibold">
                    Upload Files
                  </CardTitle>
                  <p className="text-sm text-muted-foreground">
                    Upload 1 or 2 files to find duplicates within or between
                    them
                  </p>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-4">
                    <FileUpload
                      onFileUpload={handleFileUpload}
                      handleClearAll={handleRemoveFile}
                      files={files}
                      isLoading={isLoading}
                      maxFiles={2}
                    />
                  </div>
                  {files.length > 0 && renderColumnSelection()}
                  {files.length > 0 && selectedColumns.length >= 2 && (
                    <div className="flex gap-2">
                      <Button
                        onClick={handleRemoveDuplicates}
                        disabled={isLoading || files.length > 1}
                        className="w-full"
                      >
                        {isLoading ? "Processing..." : "Find Duplicates"}
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
                      <p className="text-sm text-muted-foreground text-center">
                        Processing your file...
                      </p>
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
            {files.length > 1 ? (
              <ColumnMapper
                file1={files[0]}
                file2={files[1]}
                onMappingComplete={handleMappingComplete}
                setAvailableColumns={setAvailableColumns}
              />
            ) : null} 
              <FilePreview
                file={files[0]}
                hidden={files.length > 1}
                setAvailableColumns={setAvailableColumns}
              />
            
          </div>
        )}

        {/* Training interface */}
        {trainingData && !duplicates.length && (
          <div className="flex justify-end mb-4">
            <Button
              variant="destructive"
              onClick={handleClearAll}
              className="button-hover shadow-md"
            >
              <RotateCcw className="mr-2 h-4 w-4" />
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

        {duplicates.length === 0 &&
          !isLoading &&
          files.length > 0 &&
          apiCalled &&
          !trainingData && (
            <div className="text-center p-8 bg-white/5 backdrop-blur-sm rounded-lg border border-muted shadow-lg">
              <div className="inline-block rounded-full bg-green-100 p-3 animate-float">
                <CheckCircle2 className="h-6 w-6 text-green-600" />
              </div>
              <p className="mt-2 text-muted-foreground">
                No duplicates found in your file.
              </p>
            </div>
          )}

        {duplicates.length > 0 && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <h2 className="text-2xl font-semibold bg-gradient-to-r from-primary to-primary/80 bg-clip-text text-transparent">
                  Duplicate Groups Found
                </h2>
                <Button
                  variant="destructive"
                  onClick={handleClearAll}
                  className="button-hover shadow-md"
                >
                  <RotateCcw className="mr-2 h-4 w-4" />
                  Reset
                </Button>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex gap-2">
                  <Button
                    onClick={handleRemoveAllDuplicates}
                    variant="secondary"
                    className="button-hover shadow-md flex items-center gap-2"
                    title="Select all duplicate records for removal"
                  >
                    <X className="h-4 w-4" />
                    Select All Duplicates
                  </Button>
                  <Button
                    onClick={downloadWithDuplicates}
                    variant="outline"
                    className="button-hover shadow-md flex items-center gap-2"
                    title="Download original file with all records"
                  >
                    <Download className="h-4 w-4" />
                    Download Original
                  </Button>
                  <Button
                    onClick={handleDownloadDeduplicated}
                    className="bg-gradient-to-r from-green-600 to-green-500 hover:from-green-700 hover:to-green-600 text-white button-hover shadow-md flex items-center gap-2"
                    title="Download file with selected duplicates removed"
                  >
                    <CheckCircle2 className="h-4 w-4" />
                    Download Clean File
                  </Button>
                </div>
              </div>
            </div>
            <div className="flex justify-end">
              <Select
                value={sortOption}
                onValueChange={(value) => setSortOption(value as SortOption)}
              >
                <SelectTrigger className="w-[220px]">
                  <SelectValue placeholder="Sort by..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="group-id">Sort by Group ID</SelectItem>
                  <SelectItem value="confidence-high">
                    Confidence: High to Low
                  </SelectItem>
                  <SelectItem value="confidence-low">
                    Confidence: Low to High
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-4">
              {getSortedDuplicates().map((group) => (
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
  );
}
