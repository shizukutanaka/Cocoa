import React from 'react';
import PageHeader from '@atlaskit/page-header';
import Button from '@atlaskit/button/standard-button';
import DynamicTable from '@atlaskit/dynamic-table';
import Lozenge from '@atlaskit/lozenge';
import EmptyState from '@atlaskit/empty-state';

const Dashboard: React.FC = () => {
  const head = {
    cells: [
      { key: 'name', content: '名前', isSortable: true },
      { key: 'type', content: 'タイプ', isSortable: true },
      { key: 'lastModified', content: '最終更新', isSortable: true },
      { key: 'status', content: 'ステータス' },
    ],
  };

  const actions = (
    <>
      <Button appearance="primary">新しいアバター</Button>
      <Button>コラボレーション開始</Button>
    </>
  );

  const [isLoading, setIsLoading] = React.useState(true);
  const [activities, setActivities] = React.useState<any[]>([]);

  React.useEffect(() => {
    // Simulate API call
    setTimeout(() => {
      // setActivities(rows); // To test with data
      setActivities([]); // To test empty state
      setIsLoading(false);
    }, 2000);
  }, []);

  return (
    <>
      <PageHeader actions={actions}>ダッシュボード</PageHeader>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 my-8">
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <h4 className="text-sm font-medium text-gray-600">総アバター数</h4>
          <p className="text-3xl font-bold text-gray-900 mt-2">1,234</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <h4 className="text-sm font-medium text-gray-600">アクティブユーザー</h4>
          <p className="text-3xl font-bold text-gray-900 mt-2">89</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <h4 className="text-sm font-medium text-gray-600">進行中のセッション</h4>
          <p className="text-3xl font-bold text-gray-900 mt-2">12</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <h4 className="text-sm font-medium text-gray-600">システム負荷</h4>
          <p className="text-3xl font-bold text-gray-900 mt-2">23%</p>
        </div>
      </div>

      <h2 className="text-lg font-semibold text-gray-800 mb-4">最近のアクティビティ</h2>
      <DynamicTable
        head={head}
        rows={activities}
        rowsPerPage={10}
        page={1}
        loadingSpinnerSize="large"
        isLoading={isLoading}
        isFixedSize
        onSort={() => console.log('sort')}
        onSetPage={() => console.log('set page')}
        emptyView={<EmptyState header="アクティビティがありません" description="まだ何もアクティビティがありません。新しいアバターを作成してみましょう。" />}
      />
    </>
  );
};

export default Dashboard;
