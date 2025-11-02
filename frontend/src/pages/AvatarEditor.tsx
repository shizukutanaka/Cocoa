import React from 'react';
import { AvatarCreator } from '@/components/AvatarCreator';

const AvatarEditor: React.FC = () => {
  return (
    <div className="avatar-editor-page">
      <div className="page-header">
        <h1>アバターエディター</h1>
        <p>自分だけのアバターを作成しましょう</p>
      </div>
      <div className="editor-container">
        <AvatarCreator />
      </div>
    </div>
  );
};

export default AvatarEditor;
