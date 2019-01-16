class AddUnpaidBidToOrders < ActiveRecord::Migration[5.2]
  def change
    add_column :orders, :unpaid_bid, :integer
  end
end
