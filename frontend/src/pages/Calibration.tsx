import { useState, useCallback, useEffect, useRef } from "react";
import {
  startInventory,
  stopInventory,
  setAntennaPower,
  testAlarm,
  getAntennaPower,
  getReaderStatus,
} from "../api/client";
import type { WSEvent, WSTagDetectedEvent, WSCommandResponseEvent, WSReaderStatusEvent } from "../api/types";
import { useWebSocket } from "../hooks/useWebSocket";
import { Card, CardHeader, Button, Alert, Slider, EmptyState, LoadingState, StatusBadge } from "../components";

interface LiveTag extends WSTagDetectedEvent {
  id: number;
}

interface AntennaInfo {
  ant1?: number;
  ant2?: number;
  ant3?: number;
  ant4?: number;
}

interface ReaderInfo {
  status?: string;
  uptime?: number;
  antennas?: number[];
}

type QueryType = "power" | "status" | null;

const QUERY_TIMEOUT_MS = 10000; // 10 seconds timeout

export default function Calibration() {
  const [isScanning, setIsScanning] = useState(false);
  const [liveTags, setLiveTags] = useState<LiveTag[]>([]);
  const [message, setMessage] = useState<{
    type: "success" | "error" | "info";
    text: string;
  } | null>(null);
  const [power, setPower] = useState({
    antenna1: 20,
    antenna2: 20,
    antenna3: 15,
    antenna4: 15,
  });
  const [antennaInfo, setAntennaInfo] = useState<AntennaInfo | null>(null);
  const [readerInfo, setReaderInfo] = useState<ReaderInfo | null>(null);
  const [queryingType, setQueryingType] = useState<QueryType>(null);
  const [lastQueryTime, setLastQueryTime] = useState<Date | null>(null);
  const timeoutRef = useRef<number | null>(null);

  // Clear timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const clearQueryTimeout = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  const handleWsMessage = useCallback((event: WSEvent) => {
    if (event.type === "TAG_DETECTED") {
      setLiveTags((prev) => {
        const existing = prev.findIndex((t) => t.tag_id === event.tag_id);
        if (existing >= 0) {
          const updated = [...prev];
          updated[existing] = { ...event, id: prev[existing].id };
          return updated;
        }
        return [{ ...event, id: Date.now() }, ...prev.slice(0, 49)];
      });
    } else if (event.type === "COMMAND_RESPONSE") {
      const cmdEvent = event as WSCommandResponseEvent;
      if (cmdEvent.command === "power" && cmdEvent.action === "get") {
        clearQueryTimeout();
        if (cmdEvent.status === "success" && cmdEvent.data) {
          const data = cmdEvent.data as AntennaInfo;
          setAntennaInfo(data);
          // Auto-sync sliders with received values
          setPower({
            antenna1: data.ant1 ?? 20,
            antenna2: data.ant2 ?? 20,
            antenna3: data.ant3 ?? 15,
            antenna4: data.ant4 ?? 15,
          });
          setLastQueryTime(new Date());
          setMessage({ type: "success", text: "Antenna power loaded - adjust sliders below to change" });
        } else {
          setMessage({
            type: "error",
            text: `Failed to get antenna power: ${cmdEvent.message || "Unknown error"}`
          });
        }
        setQueryingType(null);
      }
    } else if (event.type === "READER_STATUS") {
      clearQueryTimeout();
      const statusEvent = event as WSReaderStatusEvent;
      setReaderInfo({
        status: statusEvent.status,
        uptime: statusEvent.uptime,
        antennas: statusEvent.antennas,
      });
      setLastQueryTime(new Date());
      setMessage({ type: "success", text: "Reader status retrieved successfully" });
      setQueryingType(null);
    }
  }, [clearQueryTimeout]);

  useWebSocket({ onMessage: handleWsMessage });

  const handleStartScan = async () => {
    try {
      await startInventory();
      setIsScanning(true);
      setLiveTags([]);
      setMessage({ type: "success", text: "Inventory scan started" });
    } catch (e) {
      setMessage({
        type: "error",
        text: e instanceof Error ? e.message : "Failed to start scan",
      });
    }
  };

  const handleStopScan = async () => {
    try {
      await stopInventory();
      setIsScanning(false);
      setMessage({ type: "success", text: "Inventory scan stopped" });
    } catch (e) {
      setMessage({
        type: "error",
        text: e instanceof Error ? e.message : "Failed to stop scan",
      });
    }
  };

  const handleSetPower = async () => {
    try {
      await setAntennaPower(power);
      setMessage({ type: "success", text: "Antenna power updated" });
    } catch (e) {
      setMessage({
        type: "error",
        text: e instanceof Error ? e.message : "Failed to set power",
      });
    }
  };

  const handleTestAlarm = async () => {
    try {
      await testAlarm();
      setMessage({ type: "success", text: "Test alarm triggered" });
    } catch (e) {
      setMessage({
        type: "error",
        text: e instanceof Error ? e.message : "Failed to trigger alarm",
      });
    }
  };

  const handleQueryPower = async () => {
    try {
      clearQueryTimeout();
      setQueryingType("power");
      setMessage({ type: "info", text: "Querying antenna power..." });
      await getAntennaPower();

      // Set timeout for response
      timeoutRef.current = window.setTimeout(() => {
        setQueryingType(null);
        setMessage({
          type: "error",
          text: "Timeout: No response from reader. Check MQTT connection."
        });
      }, QUERY_TIMEOUT_MS);
    } catch (e) {
      clearQueryTimeout();
      setQueryingType(null);
      setMessage({
        type: "error",
        text: e instanceof Error ? e.message : "Failed to query power",
      });
    }
  };

  const handleQueryStatus = async () => {
    try {
      clearQueryTimeout();
      setQueryingType("status");
      setMessage({ type: "info", text: "Querying reader status..." });
      await getReaderStatus();

      // Set timeout for response
      timeoutRef.current = window.setTimeout(() => {
        setQueryingType(null);
        setMessage({
          type: "error",
          text: "Timeout: No response from reader. Check MQTT connection."
        });
      }, QUERY_TIMEOUT_MS);
    } catch (e) {
      clearQueryTimeout();
      setQueryingType(null);
      setMessage({
        type: "error",
        text: e instanceof Error ? e.message : "Failed to query status",
      });
    }
  };

  // Sync slider values with queried antenna power
  const handleSyncWithCurrent = () => {
    if (antennaInfo) {
      setPower({
        antenna1: antennaInfo.ant1 ?? power.antenna1,
        antenna2: antennaInfo.ant2 ?? power.antenna2,
        antenna3: antennaInfo.ant3 ?? power.antenna3,
        antenna4: antennaInfo.ant4 ?? power.antenna4,
      });
      setMessage({ type: "success", text: "Slider values synced with current power" });
    }
  };

  // Helper to get difference between current and set values
  const getPowerDiff = (antennaNum: number): number | null => {
    if (!antennaInfo) return null;
    const currentKey = `ant${antennaNum}` as keyof AntennaInfo;
    const setKey = `antenna${antennaNum}` as keyof typeof power;
    const current = antennaInfo[currentKey];
    const setValue = power[setKey];
    if (current === undefined) return null;
    return setValue - current;
  };

  // Check if any values have changed from current
  const hasChanges = antennaInfo && (
    power.antenna1 !== antennaInfo.ant1 ||
    power.antenna2 !== antennaInfo.ant2 ||
    power.antenna3 !== antennaInfo.ant3 ||
    power.antenna4 !== antennaInfo.ant4
  );

  const alertVariant = message?.type === "success" ? "success" : message?.type === "info" ? "info" : "error";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Calibration</h1>

      {message && (
        <Alert variant={alertVariant} loading={message.type === "info"}>
          {message.text}
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Inventory Control */}
        <Card>
          <CardHeader title="Inventory Scan" icon="📦" />
          <div className="flex space-x-4">
            <Button
              onClick={handleStartScan}
              // disabled={isScanning}
              variant="success"
              className="flex-1"
            >
              Start Scan
            </Button>
            <Button
              onClick={handleStopScan}
              // disabled={!isScanning}
              variant="danger"
              className="flex-1"
            >
              Stop Scan
            </Button>
          </div>
          <p className="mt-2 text-sm text-gray-500">
            Status:{" "}
            {isScanning ? (
              <span className="text-success-600 font-medium">Scanning...</span>
            ) : (
              "Idle"
            )}
          </p>
        </Card>

        {/* Test Alarm */}
        <Card>
          <CardHeader title="Test Alarm" icon="🔔" />
          <Button
            onClick={handleTestAlarm}
            variant="warning"
            size="lg"
            className="w-full"
          >
            Trigger Test Alarm
          </Button>
          <p className="mt-2 text-sm text-gray-500">
            Sends GPO pulse to test alarm hardware
          </p>
        </Card>

        {/* Unified Antenna Power Configuration */}
        <Card className="lg:col-span-2">
          <CardHeader
            title="Antenna Power Configuration"
            icon="📡"
            subtitle={lastQueryTime ? `Last synced: ${lastQueryTime.toLocaleTimeString()}` : undefined}
            action={
              <Button
                onClick={handleQueryPower}
                disabled={queryingType !== null}
                loading={queryingType === "power"}
                size="sm"
                icon={queryingType !== "power" ? "🔄" : undefined}
              >
                {antennaInfo ? "Refresh" : "Load Current"}
              </Button>
            }
          />

          {/* Initial state - no data loaded yet */}
          {/* {!antennaInfo && queryingType !== "power" && (
            <EmptyState
              icon="📡"
              title='Click "Load Current" to fetch antenna power from reader'
              description="This will load current settings and allow you to adjust them"
            />
          )} */}

          {/* Loading state */}
          {queryingType === "power" && !antennaInfo && (
            <LoadingState message="Querying reader..." />
          )}

          {/* Antenna Power Grid - shown when data is loaded */}
            <>
              {/* Change indicator */}
              {hasChanges && (
                <Alert variant="warning">
                  <div className="flex justify-between items-center w-full">
                    <span>You have unsaved changes</span>
                    <button
                      onClick={handleSyncWithCurrent}
                      className="text-warning-700 hover:text-warning-800 underline text-xs"
                    >
                      Reset to current
                    </button>
                  </div>
                </Alert>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mt-4">
                {[1, 2, 3, 4].map((num) => {
                  const setKey = `antenna${num}` as keyof typeof power;
                  const currentKey = `ant${num}` as keyof AntennaInfo;
                  const setValue = power[setKey];
                  const currentValue = antennaInfo?.[currentKey];
                  const diff = getPowerDiff(num);
                  const isChanged = diff !== null && diff !== 0;

                  return (
                    <Slider
                      key={num}
                      label={`Antenna ${num}`}
                      value={setValue}
                      min={0}
                      max={30}
                      unit="dBm"
                      changed={isChanged}
                      originalValue={currentValue}
                      diff={diff}
                      onChange={(e) =>
                        setPower({
                          ...power,
                          [`antenna${num}`]: parseInt((e.target as HTMLInputElement).value),
                        })
                      }
                    />
                  );
                })}
              </div>

              {/* Action Buttons */}
              <div className="mt-6 flex flex-wrap gap-4">
                <Button
                  onClick={handleSetPower}
                  disabled={!hasChanges}
                  variant={hasChanges ? "primary" : "ghost"}
                >
                  Apply Changes
                </Button>
                  <Button
                    onClick={handleSyncWithCurrent}
                    variant="secondary"
                  >
                    Reset All
                  </Button>
              </div>
            </>
        </Card>

        {/* Reader Status - Separate Card */}
        <Card className="lg:col-span-2">
          <CardHeader
            title="Reader Status"
            icon="🔌"
            action={
              <Button
                onClick={handleQueryStatus}
                // disabled={queryingType !== null}
                loading={queryingType === "status"}
                variant="secondary"
                size="sm"
              >
                Query Status
              </Button>
            }
          />

          {readerInfo ? (
            <div className="grid grid-cols-3 gap-4">
              <div className="p-4 bg-gray-50 rounded-lg text-center">
                <div className="text-xs text-gray-500 uppercase mb-1">Status</div>
                <div className={`text-lg font-semibold ${
                  readerInfo.status === 'online' ? 'text-success-600' : 'text-danger-600'
                }`}>
                  {readerInfo.status}
                </div>
              </div>
              <div className="p-4 bg-gray-50 rounded-lg text-center">
                <div className="text-xs text-gray-500 uppercase mb-1">Uptime</div>
                <div className="text-lg font-semibold text-gray-700">{readerInfo.uptime}s</div>
              </div>
              <div className="p-4 bg-gray-50 rounded-lg text-center">
                <div className="text-xs text-gray-500 uppercase mb-1">Antennas</div>
                <div className="text-lg font-semibold text-gray-700">
                  {readerInfo.antennas?.join(", ") || "—"}
                </div>
              </div>
            </div>
          ) : (
            <EmptyState
              icon="🔌"
              title='Click "Query Status" to check reader connectivity'
            />
          )}
        </Card>
      </div>

      {/* Live Tags */}
      <Card padding="none">
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h2 className="text-lg font-medium">Live Tags ({liveTags.length})</h2>
          <Button
            onClick={() => setLiveTags([])}
            variant="ghost"
            size="sm"
          >
            Clear
          </Button>
        </div>
        <div className="max-h-96 overflow-y-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50 sticky top-0">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Tag ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  RSSI
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Antenna
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  State
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {liveTags.length === 0 ? (
                <tr>
                  <td
                    colSpan={4}
                    className="px-6 py-4 text-center text-gray-500"
                  >
                    No tags detected
                  </td>
                </tr>
              ) : (
                liveTags.map((tag) => (
                  <tr key={tag.id}>
                    <td className="px-6 py-2 font-mono text-sm">
                      {tag.tag_id}
                    </td>
                    <td className="px-6 py-2 text-sm">
                      {tag.rssi?.toFixed(1)} dBm
                    </td>
                    <td className="px-6 py-2 text-sm">{tag.antenna}</td>
                    <td className="px-6 py-2">
                      <StatusBadge variant={tag.decision === "PASS" ? "success" : "danger"}>
                        {tag.decision}
                      </StatusBadge>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
