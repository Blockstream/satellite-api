class AddStatusAndAmountToInvoices < ActiveRecord::Migration[5.2]
  def change
    add_column :invoices, :status, :integer
    add_column :invoices, :amount, :integer
    add_index :invoices, :status
  end
end
