// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title L2AtomicArbitrageExecutor
 * @dev Atomic DEX-to-DEX Arbitrage Executor for Base L2 (Uniswap v3, Aerodrome, etc.)
 * Ensures zero-loss atomic execution using in-flight revert checks.
 */

interface IERC20 {
    function balanceOf(address account) external view returns (uint256);
    function transfer(address recipient, uint256 amount) external returns (bool);
    function approve(address spender, uint256 amount) external returns (bool);
}

interface ISwapRouter {
    function exactInputSingle(bytes calldata params) external payable returns (uint256 amountOut);
}

contract L2AtomicArbitrageExecutor {
    address public owner;

    event ArbitrageExecuted(
        address indexed tokenIn,
        uint256 amountIn,
        uint256 amountOut,
        uint256 netProfit
    );

    event EmergencyWithdraw(address indexed token, uint256 amount);

    modifier onlyOwner() {
        require(msg.sender == owner, "Caller is not owner");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    receive() external payable {}

    /**
     * @dev Executes a two-leg atomic arbitrage swap.
     * @param tokenA Address of base token (e.g., USDC)
     * @param tokenB Address of target token (e.g., WETH, AERO, cbBTC)
     * @param amountIn Working trade size in tokenA (e.g., 2950 USDC)
     * @param minNetProfit Minimum required net profit in tokenA (e.g., 6.0 USDC)
     * @param routerLeg1 Address of first DEX router (e.g., Uniswap v3 Router)
     * @param routerLeg2 Address of second DEX router (e.g., Aerodrome Router)
     * @param swapDataLeg1 Encoded calldata for Leg 1 swap
     * @param swapDataLeg2 Encoded calldata for Leg 2 swap
     */
    function executeAtomicArbitrage(
        address tokenA,
        address tokenB,
        uint256 amountIn,
        uint256 minNetProfit,
        address routerLeg1,
        address routerLeg2,
        bytes calldata swapDataLeg1,
        bytes calldata swapDataLeg2
    ) external onlyOwner returns (uint256 netProfit) {
        uint256 initialBalance = IERC20(tokenA).balanceOf(address(this));
        require(initialBalance >= amountIn, "Insufficient working balance in contract");

        // 1. Approve Leg 1 Router
        IERC20(tokenA).approve(routerLeg1, amountIn);

        // 2. Execute Leg 1 Swap (Token A -> Token B)
        (bool successLeg1, ) = routerLeg1.call(swapDataLeg1);
        require(successLeg1, "Leg 1 Swap Failed");

        uint256 tokenBBalance = IERC20(tokenB).balanceOf(address(this));
        require(tokenBBalance > 0, "Zero output from Leg 1");

        // 3. Approve Leg 2 Router
        IERC20(tokenB).approve(routerLeg2, tokenBBalance);

        // 4. Execute Leg 2 Swap (Token B -> Token A)
        (bool successLeg2, ) = routerLeg2.call(swapDataLeg2);
        require(successLeg2, "Leg 2 Swap Failed");

        // 5. Atomic Revert Protection Check
        uint256 finalBalance = IERC20(tokenA).balanceOf(address(this));
        require(
            finalBalance >= initialBalance + minNetProfit,
            "Arbitrage Unprofitable: Reverting Transaction"
        );

        netProfit = finalBalance - initialBalance;
        emit ArbitrageExecuted(tokenA, amountIn, finalBalance, netProfit);
        return netProfit;
    }

    /**
     * @dev Withdraws ERC20 tokens back to owner wallet.
     */
    function withdrawToken(address token) external onlyOwner {
        uint256 balance = IERC20(token).balanceOf(address(this));
        require(balance > 0, "No token balance");
        IERC20(token).transfer(owner, balance);
        emit EmergencyWithdraw(token, balance);
    }

    /**
     * @dev Withdraws ETH back to owner wallet.
     */
    function withdrawETH() external onlyOwner {
        uint256 balance = address(this).balance;
        require(balance > 0, "No ETH balance");
        payable(owner).transfer(balance);
        emit EmergencyWithdraw(address(0), balance);
    }
}
