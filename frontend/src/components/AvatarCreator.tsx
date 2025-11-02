import React, { useState, useCallback, useMemo } from 'react';
import { AvatarOptionsPanel } from '@/components/AvatarOptionsPanel';
import { AvatarPreview } from '@/components/AvatarPreview';
import { AvatarWizard } from '@/components/AvatarWizard';
import { InteractiveAIChat } from '@/components/InteractiveAIChat';
import { AvatarVideoCreator } from '@/components/AvatarVideoCreator';
import { PhotoToAvatarUploader } from '@/components/PhotoToAvatarUploader';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import { NotificationToast } from '@/components/NotificationToast';
import { GenerationOptions } from '@/types/avatarTypes';
import { DEFAULT_AVATAR_OPTIONS } from '@/constants/avatarConstants';
import Button from '@atlaskit/button/standard-button';
import MagicWandIcon from '@atlaskit/icon/glyph/magic-wand';
import ExportIcon from '@atlaskit/icon/glyph/export';
import MessageIcon from '@atlaskit/icon/glyph/comment';
import VideoIcon from '@atlaskit/icon/glyph/media-services/video';
import CameraIcon from '@atlaskit/icon/glyph/camera';
import Modal, { ModalTransition } from '@atlaskit/modal-dialog';

export const AvatarCreator: React.FC = () => {
  const [options, setOptions] = useState<GenerationOptions>(DEFAULT_AVATAR_OPTIONS);
  const [isGenerating, setIsGenerating] = useState(false);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [wizardMode, setWizardMode] = useState(false);
  const [showExportModal, setShowExportModal] = useState(false);
  const [showAIChat, setShowAIChat] = useState(false);
  const [showVideoCreator, setShowVideoCreator] = useState(false);
  const [showPhotoUploader, setShowPhotoUploader] = useState(false);

  const handleOptionChange = useCallback((key: keyof GenerationOptions, value: any) => {
    setOptions(prev => ({ ...prev, [key]: value }));
  }, []);

  const handleGenerate = useCallback(() => {
    setIsGenerating(true);
    setNotification(null);

    // シミュレーション生成
    setTimeout(() => {
      setIsGenerating(false);
      setNotification({ message: 'アバターが正常に生成されました！', type: 'success' });
    }, 2000);
  }, []);

  const handleWizardComplete = useCallback((wizardOptions: GenerationOptions) => {
    setOptions(wizardOptions);
    setWizardMode(false);
    setNotification({ message: 'ウィザードが完了しました！オプションを確認してください。', type: 'success' });
  }, []);

  const handleWizardCancel = useCallback(() => {
    setWizardMode(false);
  }, []);

  const handleExportForVRChat = useCallback(async () => {
    try {
      // VRChatエクスポート処理をシミュレート
      setNotification({ message: 'VRChat用エクスポートを開始中...', type: 'success' });

      // 実際の実装ではバックエンドAPIを呼び出す
      await new Promise(resolve => setTimeout(resolve, 2000));

      setNotification({
        message: 'VRChat用エクスポートが完了しました！Unityパッケージがダウンロード可能です。',
        type: 'success'
      });
      setShowExportModal(false);
    } catch (error) {
      setNotification({
        message: 'エクスポートに失敗しました。もう一度お試しください。',
        type: 'error'
      });
    }
  }, []);

  const previewKey = useMemo(() => JSON.stringify(options), [options]);

  if (wizardMode) {
    return (
      <div style={{
        padding: '20px',
        backgroundColor: '#f8f9fa',
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <AvatarWizard
          onComplete={handleWizardComplete}
          onCancel={handleWizardCancel}
        />
      </div>
    );
  }

  return (
    <div className="avatar-creator" style={{ padding: '20px' }}>
      {/* ヘッダー */}
      <div style={{
        marginBottom: '30px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <h1 style={{ margin: 0, fontSize: '2rem', color: '#333' }}>
          アバタークリエイター
        </h1>
        <div style={{ display: 'flex', gap: '10px' }}>
          <Button
            iconBefore={<MagicWandIcon label="wizard" />}
            appearance="primary"
            onClick={() => setWizardMode(true)}
          >
            ウィザードモードで作成
          </Button>
          <Button
            iconBefore={<MessageIcon label="ai-chat" />}
            appearance="subtle"
            onClick={() => setShowAIChat(true)}
          >
            AIチャット
          </Button>
          <Button
            iconBefore={<VideoIcon label="video" />}
            appearance="subtle"
            onClick={() => setShowVideoCreator(true)}
          >
            動画作成
          </Button>
          <Button
            iconBefore={<ExportIcon label="export" />}
            appearance="subtle"
            onClick={() => setShowExportModal(true)}
          >
            VRChatエクスポート
          </Button>
        </div>
      </div>

      {isGenerating && (
        <LoadingSpinner message="アバターを生成中..." />
      )}

      {notification && (
        <NotificationToast
          message={notification.message}
          type={notification.type}
          onClose={() => setNotification(null)}
        />
      )}

      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '30px',
        alignItems: 'start'
      }}>
        <AvatarOptionsPanel
          options={options}
          isGenerating={isGenerating}
          onOptionChange={handleOptionChange}
          onGenerate={handleGenerate}
        />
        <AvatarPreview key={previewKey} options={options} />
      </div>

      {/* 動画作成モーダル */}
      <ModalTransition>
        {showVideoCreator && (
          <Modal
            onClose={() => setShowVideoCreator(false)}
            heading="アバター動画作成"
            width="large"
            height="700px"
          >
            <AvatarVideoCreator
              avatarOptions={options}
              onClose={() => setShowVideoCreator(false)}
            />
          </Modal>
        )}
      </ModalTransition>

      {/* ヘルプテキスト */}
      <div style={{
        marginTop: '30px',
        padding: '20px',
        backgroundColor: '#f0f8ff',
        borderRadius: '8px',
        border: '1px solid #bee3f8'
      }}>
        <h3 style={{ margin: '0 0 15px 0', color: '#2B6CB0' }}>
          使い方ガイド
        </h3>
        <ul style={{ margin: 0, paddingLeft: '20px', color: '#2C5282' }}>
          <li>左側のパネルでアバターのスタイル、複雑さ、色、特徴を設定できます</li>
          <li>右側のプレビューで設定変更をリアルタイムで確認できます</li>
          <li>「ウィザードモード」ボタンで初心者向けのガイド付き作成が利用できます</li>
          <li>「AIチャット」ボタンで会話可能なAIアバターと対話できます</li>
          <li>「動画作成」ボタンでアバターを使った動画を生成できます</li>
          <li>ドラッグ&ドロップで色を選択・並び替えできます</li>
          <li>「アバターを生成」ボタンでAIによる本格的な生成が可能です</li>
          <li>「VRChatエクスポート」ボタンでVRChat Avatars 3.0対応パッケージを生成できます</li>
        </ul>
      </div>
    </div>
  );
;
