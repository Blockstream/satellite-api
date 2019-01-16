class AddTxSeqNumToOrders < ActiveRecord::Migration[5.2]
  def change
    add_column :orders, :tx_seq_num, :integer
    add_index :orders, :tx_seq_num, unique: true
  end
end
