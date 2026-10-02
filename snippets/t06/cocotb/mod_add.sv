// Registered modular adder: r = (a + b) mod Q for a, b < Q, one cycle of latency.
module mod_add #(
    parameter int unsigned W = 16,
    parameter int unsigned Q = 65521          // the largest 16-bit prime
) (
    input  logic         clk,
    input  logic         rst_n,
    input  logic         in_valid,
    input  logic [W-1:0] a,
    input  logic [W-1:0] b,
    output logic         out_valid,
    output logic [W-1:0] r
);
    logic [W:0] sum, reduced;
    assign sum     = a + b;                   // W+1 bits: cannot overflow
    assign reduced = sum - Q;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            out_valid <= 1'b0;
        end else begin
            out_valid <= in_valid;
            r         <= (sum >= Q) ? reduced[W-1:0] : sum[W-1:0];
        end
    end
endmodule
