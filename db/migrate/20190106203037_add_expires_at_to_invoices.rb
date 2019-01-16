class AddExpiresAtToInvoices < ActiveRecord::Migration[5.2]
  def change
    add_column :invoices, :expires_at, :datetime
    add_index :invoices, :expires_at    
  end
end
