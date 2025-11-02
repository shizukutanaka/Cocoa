import React, { useState, useEffect } from 'react';
import PageHeader from '@atlaskit/page-header';
import Button from '@atlaskit/button/standard-button';
import DynamicTable from '@atlaskit/dynamic-table';
import Lozenge from '@atlaskit/lozenge';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';

interface SystemMetrics {
  timestamp: string;
  cpu: number;
  memory: number;
  disk_io: number;
  network_io: number;
  process_memory: number;
}

interface HealthStatus {
  status: 'healthy' | 'warning' | 'critical';
  message: string;
  last_check: string;
}

const Monitoring: React.FC = () => {
  const [metrics, setMetrics] = useState<SystemMetrics[]>([]);
  const [healthStatus, setHealthStatus] = useState<HealthStatus>({
    status: 'healthy',
    message: 'システムは正常に動作しています',
    last_check: new Date().toISOString()
  });
  const [isConnected, setIsConnected] = useState(false);
  const [realtimeData, setRealtimeData] = useState<SystemMetrics[]>([]);

  // リアルタイムデータ取得のシミュレーション
  useEffect(() => {
    const interval = setInterval(() => {
      const newMetric: SystemMetrics = {
        timestamp: new Date().toLocaleTimeString(),
        cpu: Math.random() * 100,
        memory: Math.random() * 100,
        disk_io: Math.random() * 1000,
        network_io: Math.random() * 2048,
        process_memory: Math.random() * 100
      };

      setRealtimeData(prev => [...prev.slice(-20), newMetric]); // 最新20件を保持
      setMetrics(prev => [...prev.slice(-50), newMetric]); // 履歴データとして保持
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  // ヘルスチェックのシミュレーション
  useEffect(() => {
    const interval = setInterval(() => {
      const cpuAvg = realtimeData.slice(-5).reduce((acc, curr) => acc + curr.cpu, 0) / Math.min(realtimeData.length, 5);
      const memoryAvg = realtimeData.slice(-5).reduce((acc, curr) => acc + curr.memory, 0) / Math.min(realtimeData.length, 5);

      let status: 'healthy' | 'warning' | 'critical' = 'healthy';
      let message = 'システムは正常に動作しています';

      if (cpuAvg > 80 || memoryAvg > 80) {
        status = 'warning';
        message = 'CPUまたはメモリ使用率が高くなっています';
      }
      if (cpuAvg > 95 || memoryAvg > 95) {
        status = 'critical';
        message = 'システム負荷が非常に高い状態です';
      }

      setHealthStatus({
        status,
        message,
        last_check: new Date().toISOString()
      });
    }, 5000);

    return () => clearInterval(interval);
  }, [realtimeData]);

  const getStatusLozenge = (status: string) => {
    switch (status) {
      case 'healthy':
        return <Lozenge appearance="success">正常</Lozenge>;
      case 'warning':
        return <Lozenge appearance="warning">警告</Lozenge>;
      case 'critical':
        return <Lozenge appearance="removed">危険</Lozenge>;
      default:
        return <Lozenge>不明</Lozenge>;
    }
  };

  const currentMetrics = realtimeData[realtimeData.length - 1] || {
    timestamp: 'データなし',
    cpu: 0,
    memory: 0,
    disk_io: 0,
    network_io: 0,
    process_memory: 0
  };

  const head = {
    cells: [
      { key: 'metric', content: 'メトリクス', isSortable: true },
      { key: 'value', content: '現在値', isSortable: true },
      { key: 'status', content: 'ステータス' },
      { key: 'threshold', content: '閾値' },
    ],
  };

  const rows = [
    {
      key: 'cpu',
      cells: [
        { key: 'metric', content: 'CPU使用率' },
        { key: 'value', content: `${currentMetrics.cpu.toFixed(1)}%` },
        { key: 'status', content: currentMetrics.cpu > 80 ? getStatusLozenge('warning') : getStatusLozenge('healthy') },
        { key: 'threshold', content: '> 80%' },
      ],
    },
    {
      key: 'memory',
      cells: [
        { key: 'metric', content: 'メモリ使用率' },
        { key: 'value', content: `${currentMetrics.memory.toFixed(1)}%` },
        { key: 'status', content: currentMetrics.memory > 80 ? getStatusLozenge('warning') : getStatusLozenge('healthy') },
        { key: 'threshold', content: '> 80%' },
      ],
    },
    {
      key: 'disk_io',
      cells: [
        { key: 'metric', content: 'ディスクI/O' },
        { key: 'value', content: `${currentMetrics.disk_io.toFixed(0)} KB/s` },
        { key: 'status', content: getStatusLozenge('healthy') },
        { key: 'threshold', content: '> 1000 KB/s' },
      ],
    },
    {
      key: 'network_io',
      cells: [
        { key: 'metric', content: 'ネットワークI/O' },
        { key: 'value', content: `${currentMetrics.network_io.toFixed(0)} KB/s` },
        { key: 'status', content: getStatusLozenge('healthy') },
        { key: 'threshold', content: '> 2048 KB/s' },
      ],
    },
  ];

  return (
    <>
      <PageHeader
        actions={
          <>
            <Button appearance="primary" onClick={() => setRealtimeData([])}>
              データリセット
            </Button>
            <Button>エクスポート</Button>
          </>
        }
      >
        システム監視
      </PageHeader>

      {/* システムヘルスステータス */}
      <div className="mb-8">
        <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">システムヘルスステータス</h3>
            {getStatusLozenge(healthStatus.status)}
          </div>
          <p className="text-gray-600 mb-2">{healthStatus.message}</p>
          <p className="text-sm text-gray-500">最終チェック: {new Date(healthStatus.last_check).toLocaleString()}</p>
        </div>
      </div>

      {/* 現在のメトリクス概要 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <h4 className="text-sm font-medium text-gray-600">CPU使用率</h4>
          <p className="text-3xl font-bold text-gray-900 mt-2">{currentMetrics.cpu.toFixed(1)}%</p>
          <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
            <div
              className="bg-blue-600 h-2 rounded-full"
              style={{ width: `${Math.min(currentMetrics.cpu, 100)}%` }}
            ></div>
          </div>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <h4 className="text-sm font-medium text-gray-600">メモリ使用率</h4>
          <p className="text-3xl font-bold text-gray-900 mt-2">{currentMetrics.memory.toFixed(1)}%</p>
          <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
            <div
              className="bg-green-600 h-2 rounded-full"
              style={{ width: `${Math.min(currentMetrics.memory, 100)}%` }}
            ></div>
          </div>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <h4 className="text-sm font-medium text-gray-600">ディスクI/O</h4>
          <p className="text-3xl font-bold text-gray-900 mt-2">{currentMetrics.disk_io.toFixed(0)}</p>
          <p className="text-sm text-gray-600">KB/s</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <h4 className="text-sm font-medium text-gray-600">ネットワークI/O</h4>
          <p className="text-3xl font-bold text-gray-900 mt-2">{currentMetrics.network_io.toFixed(0)}</p>
          <p className="text-sm text-gray-600">KB/s</p>
        </div>
      </div>

      {/* リアルタイムチャート */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">CPU使用率トレンド</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={realtimeData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="timestamp" />
              <YAxis domain={[0, 100]} />
              <Tooltip />
              <Line type="monotone" dataKey="cpu" stroke="#3B82F6" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">メモリ使用率トレンド</h3>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={realtimeData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="timestamp" />
              <YAxis domain={[0, 100]} />
              <Tooltip />
              <Area type="monotone" dataKey="memory" stroke="#10B981" fill="#10B981" fillOpacity={0.3} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 詳細メトリクステーブル */}
      <div className="bg-white border border-gray-200 rounded-lg shadow-sm">
        <div className="p-6 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">詳細メトリクス</h3>
        </div>
        <div className="p-6">
          <DynamicTable
            head={head}
            rows={rows}
            rowsPerPage={10}
            defaultPage={1}
            isLoading={false}
            isFixedSize={false}
          />
        </div>
      </div>

      {/* 接続状態表示 */}
      <div className="mt-6 text-center">
        <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
          isConnected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
        }`}>
          <div className={`w-2 h-2 rounded-full mr-2 ${
            isConnected ? 'bg-green-500' : 'bg-red-500'
          }`}></div>
          {isConnected ? 'リアルタイム接続中' : '接続切断'}
        </div>
      </div>
    </>
  );
};

export default Monitoring;
