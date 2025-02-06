"use client"

import { useState } from "react"
import { Check, X, HelpCircle, ArrowRight } from "lucide-react"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"

interface Record {
  Customer: string
  "Name 1": string
  "Name 2": string
  Street: string
  "Postal Code": string
  City: string
  Region: string
  Country: string
  [key: string]: string  // Add index signature for dynamic access
}

interface RecordComparisonProps {
  currentPair: [Record, Record]
  totalResponses: number
  yesResponses: number
  noResponses: number
  hasEnoughResponses: boolean
  isFinishLoading: boolean
  onResponse: (response: "y" | "n" | "u") => void
  onFinish: () => void
}

export default function RecordComparison({
  currentPair,
  totalResponses,
  yesResponses,
  noResponses,
  hasEnoughResponses,
  isFinishLoading,
  onResponse,
  onFinish,
}: RecordComparisonProps) {
  const [hoveredField, setHoveredField] = useState<string | null>(null)
  const progress = (totalResponses / 15) * 100

  const renderField = (key: string, value: string, record: number) => {
    const isDifferent = currentPair[0][key] !== currentPair[1][key]

    return (
      <div
        key={`${record}-${key}`}
        className={`p-3 rounded-md transition-colors duration-200 ${
          hoveredField === key ? "bg-muted" : ""
        } ${isDifferent ? "border-l-4 border-yellow-400" : ""}`}
        onMouseEnter={() => setHoveredField(key)}
        onMouseLeave={() => setHoveredField(null)}
      >
        <dt className="text-sm font-medium text-muted-foreground mb-1">{key}</dt>
        <dd className="text-base font-semibold">{value || "—"}</dd>
      </div>
    )
  }

  return (
    <Card className="w-full max-w-4xl mx-auto shadow-lg">
      <CardHeader className="space-y-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-2xl">Are these records duplicates?</CardTitle>
          <div className="flex items-center gap-2 text-sm">
            <span className="px-2 py-1 bg-green-100 text-green-700 rounded-md">Yes: {yesResponses}/2</span>
            <span className="px-2 py-1 bg-red-100 text-red-700 rounded-md">No: {noResponses}/2</span>
          </div>
        </div>
        <div className="space-y-2">
          <div className="flex justify-between text-sm text-muted-foreground">
            <span>Progress: {totalResponses}/15 responses</span>
            <span>{Math.round(progress)}%</span>
          </div>
          <Progress value={progress} className="h-2" />
        </div>
      </CardHeader>

      <CardContent>
        <div className="grid md:grid-cols-2 gap-6">
          {[0, 1].map((index) => (
            <div key={index} className="space-y-4">
              <h3 className="text-lg font-semibold flex items-center gap-2">
                Record {index + 1}
                <span className="text-sm text-muted-foreground">#{currentPair[index].Customer}</span>
              </h3>
              <dl className="grid gap-2">
                {Object.entries(currentPair[index]).map(([key, value]) => renderField(key, value as string, index))}
              </dl>
            </div>
          ))}
        </div>
      </CardContent>

      <CardFooter className="flex justify-center gap-3 pt-6">
        {isFinishLoading ? (
          <Button disabled>Processing...</Button>
        ) : (
          <>
            <Button
              onClick={() => onResponse("y")}
              variant="default"
              className="bg-green-600 hover:bg-green-700"
              size="lg"
            >
              <Check className="mr-2 h-4 w-4" />
              Yes
            </Button>
            <Button onClick={() => onResponse("n")} variant="default" className="bg-red-600 hover:bg-red-700" size="lg">
              <X className="mr-2 h-4 w-4" />
              No
            </Button>
            <Button onClick={() => onResponse("u")} variant="secondary" size="lg">
              <HelpCircle className="mr-2 h-4 w-4" />
              Uncertain
            </Button>
            {hasEnoughResponses && (
              <Button onClick={onFinish} variant="default" className="bg-blue-600 hover:bg-blue-700" size="lg">
                Finish
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            )}
          </>
        )}
      </CardFooter>
    </Card>
  )
} 