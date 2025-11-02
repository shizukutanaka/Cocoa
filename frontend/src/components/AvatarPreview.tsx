import React, { useEffect, useRef, useMemo, Suspense } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Text, Box, Sphere } from '@react-three/drei';
import { GenerationOptions } from '@/types/avatarTypes';
import * as THREE from 'three';

interface AvatarPreviewProps {
  options: GenerationOptions;
}

// 3Dアバターコンポーネント
const Avatar3D: React.FC<{ options: GenerationOptions }> = ({ options }) => {
  const meshRef = useRef<THREE.Mesh>(null);

  // オプションに基づいてマテリアルを生成
  const materials = useMemo(() => {
    const primaryColor = options.colors[0] || '#3B82F6';
    const secondaryColor = options.colors[1] || '#10B981';
    const accentColor = options.colors[2] || '#F59E0B';

    return {
      primary: new THREE.MeshStandardMaterial({ color: primaryColor }),
      secondary: new THREE.MeshStandardMaterial({ color: secondaryColor }),
      accent: new THREE.MeshStandardMaterial({ color: accentColor }),
    };
  }, [options.colors]);

  // アニメーション
  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.y = Math.sin(state.clock.elapsedTime) * 0.1;
    }
  });

  return (
    <group>
      {/* 頭部 */}
      <Sphere ref={meshRef} args={[1, 32, 32]} position={[0, 1, 0]} material={materials.primary} />

      {/* 胴体 */}
      <Box args={[1.5, 2, 0.8]} position={[0, -0.5, 0]} material={materials.secondary} />

      {/* 腕 */}
      {options.features.accessories && (
        <>
          <Sphere args={[0.3, 16, 16]} position={[-1, 0.5, 0]} material={materials.accent} />
          <Sphere args={[0.3, 16, 16]} position={[1, 0.5, 0]} material={materials.accent} />
        </>
      )}

      {/* 髪（オプション） */}
      {options.features.hair && (
        <Sphere args={[1.2, 16, 16]} position={[0, 1.8, 0]} material={materials.accent} />
      )}

      {/* 目（オプション） */}
      {options.features.eyes && (
        <>
          <Sphere args={[0.1, 8, 8]} position={[-0.3, 1.2, 0.8]} material={new THREE.MeshStandardMaterial({ color: '#000000' })} />
          <Sphere args={[0.1, 8, 8]} position={[0.3, 1.2, 0.8]} material={new THREE.MeshStandardMaterial({ color: '#000000' })} />
        </>
      )}

      {/* 口（オプション） */}
      {options.features.mouth && (
        <Box args={[0.3, 0.1, 0.05]} position={[0, 0.8, 0.8]} material={new THREE.MeshStandardMaterial({ color: '#FF69B4' })} />
      )}

      {/* 照明 */}
      <ambientLight intensity={0.6} />
      <directionalLight position={[10, 10, 5]} intensity={1} />
      <pointLight position={[-10, -10, -10]} intensity={0.5} />
    </group>
  );
};

// スタイル情報表示コンポーネント
const StyleInfo: React.FC<{ options: GenerationOptions }> = ({ options }) => {
  return (
    <div className="style-info">
      <Text
        position={[0, -2, 0]}
        fontSize={0.3}
        color="#333333"
        anchorX="center"
        anchorY="middle"
      >
        {`スタイル: ${options.style} | 複雑さ: ${options.complexity}`}
      </Text>
      <Text
        position={[0, -2.5, 0]}
        fontSize={0.2}
        color="#666666"
        anchorX="center"
        anchorY="middle"
      >
        {`色: ${options.colors.join(', ')}`}
      </Text>
    </div>
  );
};

// ローディングコンポーネント
const LoadingSpinner: React.FC = () => (
  <div className="loading-spinner">
    <Text position={[0, 0, 0]} fontSize={0.3} color="#666666">
      アバターを読み込み中...
    </Text>
  </div>
);

export const AvatarPreview: React.FC<AvatarPreviewProps> = ({ options }) => {
  const previewRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // プレビューエリアにフォーカスを移動
    if (previewRef.current) {
      previewRef.current.focus();
    }
  }, [options]);

  return (
    <div className="avatar-preview" role="region" aria-labelledby="preview-heading">
      <h3 id="preview-heading">リアルタイムプレビュー</h3>
      <div
        ref={previewRef}
        className="preview-area"
        tabIndex={0}
        aria-describedby="preview-description"
        style={{
          width: '100%',
          height: '400px',
          border: '1px solid #ddd',
          borderRadius: '8px',
          overflow: 'hidden'
        }}
      >
        <Canvas camera={{ position: [0, 0, 5], fov: 50 }}>
          <Suspense fallback={<LoadingSpinner />}>
            <Avatar3D options={options} />
            <StyleInfo options={options} />
            <OrbitControls enablePan={true} enableZoom={true} enableRotate={true} />
          </Suspense>
        </Canvas>

        <div className="preview-info" id="preview-description">
          <p>スタイル: {options.style}</p>
          <p>複雑さ: {options.complexity}</p>
          <p>色: {options.colors.join(', ')}</p>
          <div className="feature-status">
            <p>髪: {options.features.hair ? '有効' : '無効'}</p>
            <p>目: {options.features.eyes ? '有効' : '無効'}</p>
            <p>口: {options.features.mouth ? '有効' : '無効'}</p>
            <p>アクセサリー: {options.features.accessories ? '有効' : '無効'}</p>
          </div>
        </div>
      </div>
    </div>
  );
};
