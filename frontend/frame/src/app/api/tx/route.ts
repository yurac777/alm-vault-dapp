type FrameRequest = {
  untrustedData?: {
    address?: string;
  };
};
import { NextRequest, NextResponse } from 'next/server';
import { encodeFunctionData, parseEther } from 'viem';

// ALMZapper Address
const ZAPPER_ADDRESS = '0xaC7863162dB07857228AD263a77e43170dfC1c6F';

const ZAPPER_ABI = [
  {
    inputs: [{ internalType: 'address', name: 'receiver', type: 'address' }],
    name: 'zapAndDeposit',
    outputs: [],
    stateMutability: 'payable',
    type: 'function',
  },
];

export async function POST(req: NextRequest): Promise<NextResponse> {
  const body: FrameRequest = await req.json();

  // In production, you would validate the message signature here
  // const { isValid, message } = await getFrameMessage(body, { neynarApiKey: '...' });

  // For a transaction frame, the user's wallet address is sent in the body if connected, 
  // or we can just send the transaction data and the user's client will execute it.
  
  // The amount of ETH to zap and deposit (e.g. 0.005 ETH ~ $15)
  const ethAmount = '0.005';

  // We encode the function data. We set receiver to the user's address if possible, 
  // otherwise 0x00... will be substituted by the wallet client or we use a default.
  // Actually, untrustedData.address contains the user's connected address
  const userAddress = body.untrustedData?.address || '0x0000000000000000000000000000000000000000';

  const data = encodeFunctionData({
    abi: ZAPPER_ABI,
    functionName: 'zapAndDeposit',
    args: [userAddress],
  });

  return NextResponse.json({
    chainId: 'eip155:8453', // Base Mainnet
    method: 'eth_sendTransaction',
    params: {
      abi: ZAPPER_ABI,
      to: ZAPPER_ADDRESS,
      data: data,
      value: parseEther(ethAmount).toString(),
    },
  });
}
