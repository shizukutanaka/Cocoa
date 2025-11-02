import React from 'react';
import PageHeader from '@atlaskit/page-header';
import DynamicTable, { RowType } from '@atlaskit/dynamic-table';
import EmptyState from '@atlaskit/empty-state';
import Button from '@atlaskit/button/standard-button';
import Lozenge from '@atlaskit/lozenge';
import { useQuery } from 'react-query';

import { fetchAvatars, AvatarSummary } from '@/services/avatarService';

const tableHead = {
  cells: [
    { key: 'name', content: 'アバター名', isSortable: false },
    { key: 'creator', content: '作成者', isSortable: false },
    { key: 'createdAt', content: '作成日', isSortable: false },
    { key: 'status', content: 'ステータス', isSortable: false },
  ],
};

const statusLabelMap: Record<AvatarSummary['status'], string> = {
  active: '運用中',
  inactive: '停止中',
  archived: 'アーカイブ',
};

const formatDate = (value: string) =>
  new Intl.DateTimeFormat('ja-JP', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));

const statusAppearance: Record<AvatarSummary['status'], React.ComponentProps<typeof Lozenge>['appearance']> = {
  active: 'success',
  inactive: 'moved',
  archived: 'default',
};

const buildRows = (avatars: AvatarSummary[]): RowType[] =>
  avatars.map((avatar) => ({
    key: avatar.id,
    cells: [
      { key: `${avatar.id}-name`, content: avatar.name },
      { key: `${avatar.id}-creator`, content: avatar.creator },
      { key: `${avatar.id}-created`, content: formatDate(avatar.createdAt) },
      {
        key: `${avatar.id}-status`,
        content: (
          <Lozenge appearance={statusAppearance[avatar.status]}>
            {statusLabelMap[avatar.status]}
          </Lozenge>
        ),
      },
    ],
  }));

const AvatarList: React.FC = () => {
  const { data, isFetching, isError, refetch } = useQuery(['avatars'], fetchAvatars, {
    staleTime: 60_000,
    retry: 1,
  });

  const rows = React.useMemo(() => buildRows(data ?? []), [data]);

  const breadcrumbs = <div />;

  const pageActions = (
    <Button appearance="primary" onClick={() => {/* TODO: navigate to creation wizard */}}>
      新規アバター作成
    </Button>
  );

  const emptyView = (
    <EmptyState
      header={isError ? '一覧を取得できませんでした' : 'アバターがありません'}
      description={
        isError
          ? 'ネットワークまたは認証を確認し、再試行してください。'
          : 'まだアバターが作成されていません。最初のアバターを作成しましょう。'
      }
      primaryAction={
        isError ? (
          <Button appearance="warning" onClick={() => refetch()}>
            再試行
          </Button>
        ) : (
          <Button appearance="primary" onClick={() => {/* TODO: navigate to creation wizard */}}>
            新規アバター作成
          </Button>
        )
      }
    />
  );

  return (
    <>
      <PageHeader breadcrumbs={breadcrumbs} actions={pageActions}>
        アバター管理
      </PageHeader>
      <DynamicTable
        head={tableHead}
        rows={rows}
        rowsPerPage={10}
        page={1}
        loadingSpinnerSize="large"
        isLoading={isFetching}
        isFixedSize
        emptyView={emptyView}
      />
    </>
  );
};

export default AvatarList;
