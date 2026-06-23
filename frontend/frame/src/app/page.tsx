import type { Metadata } from 'next';

// Replace with the actual URL when deployed
const NEXT_PUBLIC_URL = process.env.NEXT_PUBLIC_HOST || 'https://alm-quant.xyz';

const frameMetadata = {
  'fc:frame': 'vNext',
  'fc:frame:image': `${NEXT_PUBLIC_URL}/frame-bg.jpg`,
  'fc:frame:image:aspect_ratio': '1.91:1',
  'fc:frame:button:1': 'Deposit ETH & Mint almUSD (~$15)',
  'fc:frame:button:1:action': 'tx',
  'fc:frame:button:1:target': `${NEXT_PUBLIC_URL}/api/tx`,
};

export const metadata: Metadata = {
  title: 'ALM Quant Vault',
  description: 'Deposit into ALM Quant Vault directly from Farcaster',
  openGraph: {
    title: 'ALM Quant Vault',
    description: 'Deposit into ALM Quant Vault directly from Farcaster',
    images: [`${NEXT_PUBLIC_URL}/frame-bg.jpg`],
  },
  other: {
    ...frameMetadata,
  },
};

export default function Page() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-24 bg-black text-white">
      <h1 className="text-4xl font-bold mb-4">ALM Vault Farcaster Frame</h1>
      <p className="text-xl text-gray-400">
        This is a Farcaster Frame endpoint. Embed this URL in a Warpcast post to allow users to deposit directly from their social feed.
      </p>
    </div>
  );
}
