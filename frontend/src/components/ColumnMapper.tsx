"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import * as XLSX from "xlsx";
import Papa from "papaparse";

interface ColumnMapperProps {
  file1: File;
  file2: File;
  onMappingComplete: (mapping: Record<string, string>, sourceFile: number, targetFile: number) => void;
  setAvailableColumns: (columns: string[]) => void;
}

export default function ColumnMapper({
  file1,
  file2,
  onMappingComplete,
  setAvailableColumns
}: ColumnMapperProps) {
  const [sourceColumns, setSourceColumns] = useState<string[]>([]);
  const [targetColumns, setTargetColumns] = useState<string[]>([]);
  const [mappings, setMappings] = useState<Record<string, string>>({});
  const [error, setError] = useState<string>("");
  const [selectedTargetColumns, setSelectedTargetColumns] = useState<string[]>(
    []
  );
  const [isProcessingFiles, setIsProcessingFiles] = useState(true);
  const [fileMeta, setFileMeta] = useState({
    source: 1,
    target: 2
  })

  useEffect(() => {
    const processFiles = async () => {
      try {
        // Handle single file case
        if (!file1 || !file2) {
          const columns = await getFileColumns(file1 || file2);
          setTargetColumns(columns);
          setSourceColumns(columns);
          setAvailableColumns(columns);
          setFileMeta({
            source: 1,
            target: 1
          });
          setIsProcessingFiles(false);
          return;
        }

        // Existing code for handling two files
        const [columns1, columns2] = await Promise.all([
          getFileColumns(file1),
          getFileColumns(file2),
        ]);

        // Store which file is source/target based on column count
        let sourceColumns: string[];
        let targetColumns: string[];
        let sourceMeta: number;
        let targetMeta: number;

        if (columns1.length >= columns2.length) {
          targetColumns = columns1;
          sourceColumns = columns2;
          sourceMeta = 2;
          targetMeta = 1;
        } else {
          targetColumns = columns2;
          sourceColumns = columns1;
          sourceMeta = 1;
          targetMeta = 2;
        }

        setTargetColumns(targetColumns);
        setSourceColumns(sourceColumns);
        setAvailableColumns(sourceColumns);
        setFileMeta({
          source: sourceMeta,
          target: targetMeta
        });

        // Auto-map columns with same names
        const initialMappings: Record<string, string> = {};
        const initialSelectedTargets: string[] = [];
        
        sourceColumns.forEach(sourceCol => {
          if (targetColumns.includes(sourceCol)) {
            initialMappings[sourceCol] = sourceCol;
            initialSelectedTargets.push(sourceCol);
          }
        });

        setMappings(initialMappings);
        setSelectedTargetColumns(initialSelectedTargets);
        setIsProcessingFiles(false);
      } catch (err) {
        console.error('Error processing files:', err);
        setError(
          "Error processing files. Please make sure they are valid CSV or XLSX files."
        );
        setIsProcessingFiles(false);
      }
    };

    processFiles();
  }, [file1, file2]);

  const getFileColumns = async (file: File): Promise<string[]> => {
    return new Promise((resolve, reject) => {
      if (file.name.endsWith(".csv")) {
        Papa.parse(file, {
          complete: (results) => {
            if (results.data && results.data.length > 0) {
              // Assume first row contains headers
              resolve(results.data[0] as string[]);
            } else {
              reject(new Error("No data found in CSV file"));
            }
          },
          error: (error) => reject(error),
          header: false,
        });
      } else if (file.name.match(/\.xlsx?$/)) {
        const reader = new FileReader();
        reader.onload = (e) => {
          try {
            const data = new Uint8Array(e.target?.result as ArrayBuffer);
            const workbook = XLSX.read(data, { type: "array" });
            const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
            const headers = XLSX.utils.sheet_to_json(firstSheet, {
              header: 1,
            })[0] as string[];
            resolve(headers);
          } catch (error) {
            reject(error);
          }
        };
        reader.onerror = (error) => reject(error);
        reader.readAsArrayBuffer(file);
      } else {
        reject(new Error("Unsupported file format"));
      }
    });
  };

  // Reset error when columns change
  useEffect(() => {
    setError("");
  }, []);

  const handleMapping = (sourceColumn: string, targetColumn: string) => {
    // Check if target column is already mapped
    if (
      selectedTargetColumns.includes(targetColumn) &&
      mappings[sourceColumn] !== targetColumn
    ) {
      setError(`Column "${targetColumn}" is already mapped to another column`);
      return;
    }

    setMappings((prev) => {
      const newMappings = { ...prev };

      // Remove old mapping if it exists
      if (newMappings[sourceColumn]) {
        setSelectedTargetColumns((prev) =>
          prev.filter((col) => col !== newMappings[sourceColumn])
        );
      }

      // Add new mapping
      newMappings[sourceColumn] = targetColumn;
      setSelectedTargetColumns((prev) => [...prev, targetColumn]);
      setError("");

      return newMappings;
    });
  };

  const handleReset = () => {
    const selects = document.querySelectorAll('select');
    selects.forEach(select => {
      select.value = '';
    });
    setMappings({});
    setSelectedTargetColumns([]);
    setError("");
  };

  const handleComplete = () => {
    // Validate all source columns are mapped
    const unmappedColumns = sourceColumns.filter((col) => !mappings[col]);
    if (unmappedColumns.length > 0) {
      setError(
        `Please map all columns. Missing mappings for: ${unmappedColumns.join(
          ", "
        )}`
      );
      return;
    }
    onMappingComplete(mappings, fileMeta.source, fileMeta.target);
  };

  const isComplete = sourceColumns.every((col) => mappings[col]);

  if (isProcessingFiles) {
    return (
      <Card className="w-full max-w-2xl mx-auto">
        <CardContent className="py-6">
          <div className="text-center">Processing files...</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full max-w-2xl mx-auto">
      <CardHeader>
        <CardTitle>Map Columns</CardTitle>
        <CardDescription>
          Map columns between your files. The file with {targetColumns.length}{" "}
          columns is set as the target format. Common columns have been automatically mapped.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-6">
          {sourceColumns.map((sourceColumn) => (
            <div
              key={sourceColumn}
              className="grid grid-cols-[1fr,auto,1fr] items-center gap-4"
            >
              <div className="mt-2 text-sm font-medium">{sourceColumn}</div>

              <div></div>

              <Select
                key={`select-${sourceColumn}-${mappings[sourceColumn] || ''}`}
                value={mappings[sourceColumn] || ''}
                onValueChange={(value) => handleMapping(sourceColumn, value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select column..." />
                </SelectTrigger>
                <SelectContent>
                  {targetColumns.map((targetColumn) => (
                    <SelectItem
                      key={targetColumn}
                      value={targetColumn}
                      disabled={selectedTargetColumns.includes(targetColumn) && mappings[sourceColumn] !== targetColumn}
                    >
                      {targetColumn}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ))}
        </div>
      </CardContent>

      <CardFooter className="flex justify-between">
        <Button 
          variant="ghost" 
          onClick={handleReset}
          className={isComplete ? "opacity-50 cursor-not-allowed" : ""}
        >
          Reset
        </Button>
        <Button variant="default" className="button-hover" onClick={handleComplete} disabled={!isComplete}>
          Complete Mapping
        </Button>
      </CardFooter>
    </Card>
  );
}
